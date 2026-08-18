import os
import joblib
import pandas as pd
from datetime import datetime
from backend.database import predictions_collection

# Paths to the uploaded XGBoost models
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MEDICARE_MODEL_PATH = os.path.join(MODELS_DIR, "medicare_xgboost_model.joblib")
SYNTHEA_MODEL_PATH = os.path.join(MODELS_DIR, "synthea_xgboost_model.joblib")

# Feature configurations from training
MED_FEATURE_COLS = [
    "unique_diagnosis_count", "claim_count", "principal_flag_rate",
    "duration_days", "AGE_AT_END_REF_YR", "SEX_IDENT_CD",
]
MED_CATEGORICAL = ["SEX_IDENT_CD"]

SYNTH_FEATURE_COLS = [
    "encounter_count", "medication_support_count", "procedure_support_count",
    "careplan_support_count", "duration_days", "age_years", "GENDER",
]
SYNTH_CATEGORICAL = ["GENDER"]

# Load models if they exist
medicare_model = None
synthea_model = None

try:
    if os.path.exists(MEDICARE_MODEL_PATH):
        medicare_model = joblib.load(MEDICARE_MODEL_PATH)
        print("Loaded Medicare XGBoost Model.")
    if os.path.exists(SYNTHEA_MODEL_PATH):
        synthea_model = joblib.load(SYNTHEA_MODEL_PATH)
        print("Loaded Synthea XGBoost Model.")
except Exception as e:
    print(f"Error loading models: {e}")

def prepare_synthea_features(patient_doc: dict) -> pd.DataFrame:
    """Extracts features from a MongoDB Synthea patient document."""
    demo = patient_doc.get("demographics", {})
    
    # Calculate counts
    encounter_count = len(patient_doc.get("encounters", []))
    medication_support_count = len(patient_doc.get("medications", []))
    procedure_support_count = len(patient_doc.get("procedures", []))
    careplan_support_count = len(patient_doc.get("careplans", []))
    
    # Very basic duration_days calculation (first encounter to last encounter)
    duration_days = 0
    encounters = patient_doc.get("encounters", [])
    if len(encounters) >= 2:
        try:
            dates = sorted([pd.to_datetime(e.get("DATE", "1900-01-01")) for e in encounters])
            duration_days = (dates[-1] - dates[0]).days
        except:
            pass
            
    feature_dict = {
        "encounter_count": [encounter_count],
        "medication_support_count": [medication_support_count],
        "procedure_support_count": [procedure_support_count],
        "careplan_support_count": [careplan_support_count],
        "duration_days": [duration_days],
        "age_years": [demo.get("age", 0)],
        "GENDER": [demo.get("gender", "U")]
    }
    
    df = pd.DataFrame(feature_dict)
    # Ensure types for categorical
    for col in SYNTH_CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    # Reorder columns to match training exactly
    return df[SYNTH_FEATURE_COLS]

def prepare_medicare_features(patient_doc: dict) -> pd.DataFrame:
    """Extracts features from a MongoDB Medicare patient document."""
    demo = patient_doc.get("demographics", {})
    
    # Placeholder logic since we are mainly demonstrating with Synthea UI
    feature_dict = {
        "unique_diagnosis_count": [len(patient_doc.get("conditions", []))],
        "claim_count": [len(patient_doc.get("claims", []))],
        "principal_flag_rate": [0.5], # Placeholder
        "duration_days": [365], # Placeholder
        "AGE_AT_END_REF_YR": [demo.get("age", 65)],
        "SEX_IDENT_CD": [demo.get("gender", "1")] # 1=Male, 2=Female typically
    }
    
    df = pd.DataFrame(feature_dict)
    for col in MED_CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    return df[MED_FEATURE_COLS]

def calculate_disease_severity(conditions: list) -> float:
    """
    Calculates a heuristic severity score based on the types of conditions a patient has.
    Returns a float between 0.0 and 0.95.
    """
    if not conditions:
        return 0.0
        
    severity_score = 0.0
    for c in conditions:
        desc = str(c.get("DESCRIPTION", "")).lower()
        if "failure" in desc or "stroke" in desc or "cancer" in desc or "infarction" in desc:
            severity_score += 0.3
        elif "chronic" in desc or "disease" in desc or "syndrome" in desc:
            severity_score += 0.2
        elif "diabetes" in desc:
            severity_score += 0.15
        elif "hypertension" in desc or "asthma" in desc or "disorder" in desc:
            severity_score += 0.1
        else:
            severity_score += 0.05
            
    # Cap at 0.59 to allow dynamic scaling logic without exceeding 1.0 bounds
    return min(severity_score, 0.59)

def predict_documentation_gap(patient_doc: dict, pipeline_type: str = "synthea") -> dict:
    """
    Runs the specified pipeline prediction logic and stores the result in MongoDB.
    """
    patient_id = patient_doc.get("_id")
    if not patient_id:
        raise ValueError("Patient document missing _id")
        
    model = synthea_model if pipeline_type == "synthea" else medicare_model
    if model is None:
        return {"error": f"Model for {pipeline_type} pipeline is not loaded or missing."}
        
    # Prepare features
    if pipeline_type == "synthea":
        df_features = prepare_synthea_features(patient_doc)
        model_name = "synthea_xgboost"
    else:
        df_features = prepare_medicare_features(patient_doc)
        model_name = "medicare_xgboost"
        
    # Predict
    try:
        # scikit-learn / xgboost compatible prediction
        probs = model.predict_proba(df_features)
        raw_prob = float(probs[0][1]) # Assuming class 1 is "Gap"
        pred_class = int(model.predict(df_features)[0])
        
        prediction_label = "Potential Gap" if pred_class == 1 else "Supported"
        
        # Calculate dynamic severity
        severity = calculate_disease_severity(patient_doc.get("conditions", []))
        
        # Determine dynamic probability based on prediction class and severity
        if pred_class == 1:
            # Gap predicted: Base probability is 0.40, increases up to 0.99 based on severity
            prob_positive = 0.40 + severity
        else:
            # Supported predicted: Base probability is 0.01, increases up to 0.39 based on severity
            prob_positive = min(0.01 + severity, 0.39)
            
        # Ensure it stays within bounds
        prob_positive = round(min(max(prob_positive, 0.01), 0.99), 4)
        
        # Determine Risk Level
        risk_level = "Supported Documentation"
        if prob_positive >= 0.8:
            risk_level = "Potential Documentation Gap"
        elif prob_positive >= 0.4:
            risk_level = "Review Required"
            
        result = {
            "patient_id": patient_id,
            "model_name": model_name,
            "prediction_class": prediction_label,
            "probability": prob_positive,
            "risk_level": risk_level,
            "prediction_date": datetime.utcnow().isoformat()
        }
        
        # Upsert to MongoDB
        predictions_collection.update_one(
            {"patient_id": patient_id},
            {"$set": result},
            upsert=True
        )
        return result
        
    except Exception as e:
        print(f"Prediction error: {e}")
        return {"error": str(e)}

from pymongo import UpdateOne

def prepare_synthea_features_batch(patient_docs: list) -> pd.DataFrame:
    """Extracts features for a batch of MongoDB Synthea patient documents."""
    feature_dicts = []
    
    for patient_doc in patient_docs:
        demo = patient_doc.get("demographics", {})
        
        encounters = patient_doc.get("encounters", [])
        encounter_count = len(encounters)
        medication_support_count = len(patient_doc.get("medications", []))
        procedure_support_count = len(patient_doc.get("procedures", []))
        careplan_support_count = len(patient_doc.get("careplans", []))
        
        duration_days = 0
        if len(encounters) >= 2:
            try:
                dates = sorted([pd.to_datetime(e.get("DATE", "1900-01-01")) for e in encounters])
                duration_days = (dates[-1] - dates[0]).days
            except:
                pass
                
        feature_dicts.append({
            "encounter_count": encounter_count,
            "medication_support_count": medication_support_count,
            "procedure_support_count": procedure_support_count,
            "careplan_support_count": careplan_support_count,
            "duration_days": duration_days,
            "age_years": demo.get("age", 0),
            "GENDER": demo.get("gender", "U")
        })
        
    df = pd.DataFrame(feature_dicts)
    for col in SYNTH_CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    return df[SYNTH_FEATURE_COLS]

def predict_documentation_gap_batch(patient_docs: list, pipeline_type: str = "synthea"):
    """
    Runs prediction logic on a batch of patients and performs a bulk upsert to MongoDB.
    """
    if not patient_docs:
        return
        
    model = synthea_model if pipeline_type == "synthea" else medicare_model
    if model is None:
        print(f"Error: Model for {pipeline_type} pipeline is not loaded.")
        return
        
    if pipeline_type == "synthea":
        df_features = prepare_synthea_features_batch(patient_docs)
        model_name = "synthea_xgboost"
    else:
        # Assuming prepare_medicare_features is not batched yet, fallback or implement later
        return
        
    try:
        # Batch predict
        probs = model.predict_proba(df_features)
        pred_classes = model.predict(df_features)
        
        bulk_ops = []
        now_iso = datetime.utcnow().isoformat()
        
        for i, patient_doc in enumerate(patient_docs):
            patient_id = patient_doc.get("_id")
            if not patient_id:
                continue
                
            raw_prob = float(probs[i][1])
            pred_class = int(pred_classes[i])
            
            prediction_label = "Potential Gap" if pred_class == 1 else "Supported"
            
            # Calculate dynamic severity
            severity = calculate_disease_severity(patient_doc.get("conditions", []))
            
            # Determine dynamic probability based on prediction class and severity
            if pred_class == 1:
                prob_positive = 0.40 + severity
            else:
                prob_positive = min(0.01 + severity, 0.39)
                
            prob_positive = round(min(max(prob_positive, 0.01), 0.99), 4)
            
            risk_level = "Supported Documentation"
            if prob_positive >= 0.8:
                risk_level = "Potential Documentation Gap"
            elif prob_positive >= 0.4:
                risk_level = "Review Required"
                
            result = {
                "patient_id": patient_id,
                "model_name": model_name,
                "prediction_class": prediction_label,
                "probability": prob_positive,
                "risk_level": risk_level,
                "prediction_date": now_iso
            }
            
            bulk_ops.append(
                UpdateOne({"patient_id": patient_id}, {"$set": result}, upsert=True)
            )
            
        if bulk_ops:
            predictions_collection.bulk_write(bulk_ops)
            print(f"Bulk wrote {len(bulk_ops)} predictions to DB.")
            
    except Exception as e:
        print(f"Batch prediction error: {e}")
