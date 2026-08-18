import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Any
import os
import zipfile
import tempfile

from backend.database import patients_collection, predictions_collection, explanations_collection, admins_collection
from backend.models import PatientDocument, PredictionRecord, LLMExplanation
from backend.ingest import process_synthea_folder
from pydantic import BaseModel
from fastapi import Depends, Response
from backend.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    get_current_admin,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta
from backend.report_generator import generate_patient_pdf, generate_bulk_summary_pdf

app = FastAPI(title="HCC Documentation-Gap System")

class AdminUser(BaseModel):
    email: str
    password: str

class BulkReportRequest(BaseModel):
    patient_ids: List[str]

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints

@app.post("/api/auth/register")
def register_admin(user: AdminUser):
    if admins_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    admins_collection.insert_one({
        "email": user.email,
        "hashed_password": hashed_password
    })
    return {"message": "Admin created successfully"}

@app.post("/api/auth/login")
def login_admin(user: AdminUser):
    db_user = admins_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/stats")
def get_dashboard_stats(current_admin: str = Depends(get_current_admin)):
    """Returns overall statistics for the dashboard."""
    total_patients = patients_collection.count_documents({})
    # Count only predictions that have been manually reviewed
    patients_reviewed = predictions_collection.count_documents({"human_reviewed": True})
    high_risk_count = predictions_collection.count_documents({"risk_level": "Potential Documentation Gap"})
    medium_risk_count = predictions_collection.count_documents({"risk_level": "Review Required"})
    low_risk_count = predictions_collection.count_documents({"risk_level": "Supported Documentation"})
    
    # Calculate total documents processed (conditions + medications + encounters)
    pipeline = [
        {"$project": {
            "doc_count": {
                "$add": [
                    {"$size": {"$ifNull": ["$conditions", []]}},
                    {"$size": {"$ifNull": ["$medications", []]}},
                    {"$size": {"$ifNull": ["$encounters", []]}}
                ]
            }
        }},
        {"$group": {"_id": None, "total": {"$sum": "$doc_count"}}}
    ]
    doc_stats = list(patients_collection.aggregate(pipeline))
    documents_processed = doc_stats[0]["total"] if doc_stats else 0
    
    return {
        "total_patients": total_patients,
        "patients_reviewed": patients_reviewed,
        "documents_processed": documents_processed,
        "potential_gaps": high_risk_count,
        "high_risk": high_risk_count,
        "medium_risk": medium_risk_count,
        "low_risk": low_risk_count,
    }

# Pandas converts empty CSV cells to NaN, which breaks JSON serialization
def clean_nan(obj):
    import math
    if isinstance(obj, float) and math.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(i) for i in obj]
    return obj

@app.get("/api/patients")
def get_patients(limit: int = 15000, skip: int = 0, current_admin: str = Depends(get_current_admin)):
    """Returns a list of patients that have been processed with predictions."""
    pipeline = [
        {"$sort": {"prediction_date": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient_info"
            }
        },
        {"$unwind": { "path": "$patient_info", "preserveNullAndEmptyArrays": True }},
        {
            "$project": {
                "_id": 0,
                "patient_id": 1,
                "risk_level": { "$ifNull": [ "$risk_level", "Unknown" ] },
                "prediction_class": { "$ifNull": [ "$prediction_class", "Unknown" ] },
                "probability": { "$ifNull": [ "$probability", 0.0 ] },
                "review_status": { "$ifNull": [ "$review_status", "Pending" ] },
                "age": { "$ifNull": [ "$patient_info.demographics.age", 0 ] },
                "gender": { "$ifNull": [ "$patient_info.demographics.gender", "U" ] }
            }
        }
    ]
    results = list(predictions_collection.aggregate(pipeline))
    return clean_nan(results)

@app.get("/api/patient/{patient_id}")
def get_patient_details(patient_id: str, current_admin: str = Depends(get_current_admin)):
    """Returns detailed information and explanation for a specific patient."""
    patient = patients_collection.find_one({"_id": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    prediction = predictions_collection.find_one({"patient_id": patient_id}, sort=[("prediction_date", -1)])
    explanation = explanations_collection.find_one({"patient_id": patient_id}, sort=[("created_at", -1)])
    
    if explanation is None and prediction:
        from backend.llm_service import generate_explanation
        new_exp = generate_explanation(patient, prediction)
        from datetime import datetime
        explanations_collection.insert_one({
            "patient_id": patient_id,
            "prediction_id": str(prediction.get("_id", "")),
            "explanation": new_exp,
            "created_at": datetime.utcnow().isoformat()
        })
        explanation = {"explanation": new_exp}
        
    # FastAPI cannot serialize MongoDB ObjectId, so convert them to strings
    if patient and "_id" in patient:
        patient["_id"] = str(patient["_id"])
    if prediction and "_id" in prediction:
        prediction["_id"] = str(prediction["_id"])
    if explanation and "_id" in explanation:
        explanation["_id"] = str(explanation["_id"])
        
    patient = clean_nan(patient)
    
    return {
        "patient": patient,
        "prediction": prediction,
        "explanation": explanation["explanation"] if explanation else "Explanation not yet generated."
    }

@app.get("/api/patient/{patient_id}/report")
def download_patient_report(patient_id: str, current_admin: str = Depends(get_current_admin)):
    """Generates and downloads a PDF report for the patient."""
    patient = patients_collection.find_one({"_id": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    prediction = predictions_collection.find_one({"patient_id": patient_id}) or {}
    explanation = explanations_collection.find_one({"patient_id": patient_id}) or {}
    
    patient_clean = clean_nan(patient)
    prediction_clean = clean_nan(prediction)
    explanation_clean = clean_nan(explanation)
    
    pdf_buffer = generate_patient_pdf(patient_clean, prediction_clean, explanation_clean)
    
    headers = {
        "Content-Disposition": f"attachment; filename=HCC_Patient_Report_{patient_id}.pdf"
    }
    return Response(content=pdf_buffer.getvalue(), media_type="application/pdf", headers=headers)

@app.post("/api/report/bulk")
def download_bulk_report(request: BulkReportRequest, current_admin: str = Depends(get_current_admin)):
    """Generates a bulk PDF report for the requested patient IDs."""
    if not request.patient_ids:
        raise HTTPException(status_code=400, detail="No patient IDs provided")
        
    pipeline = [
        {"$match": {"patient_id": {"$in": request.patient_ids}}},
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient_info"
            }
        },
        {"$unwind": { "path": "$patient_info", "preserveNullAndEmptyArrays": True }},
        {
            "$project": {
                "_id": 0,
                "patient_id": 1,
                "risk_level": { "$ifNull": [ "$risk_level", "Unknown" ] },
                "prediction_class": { "$ifNull": [ "$prediction_class", "Unknown" ] },
                "probability": { "$ifNull": [ "$probability", 0.0 ] },
                "review_status": { "$ifNull": [ "$review_status", "Pending" ] },
                "age": { "$ifNull": [ "$patient_info.demographics.age", 0 ] },
                "gender": { "$ifNull": [ "$patient_info.demographics.gender", "U" ] }
            }
        }
    ]
    
    patients_data = list(predictions_collection.aggregate(pipeline))
    patients_data_clean = clean_nan(patients_data)
    
    pdf_buffer = generate_bulk_summary_pdf(patients_data_clean)
    
    headers = {
        "Content-Disposition": "attachment; filename=HCC_Filtered_Summary_Report.pdf"
    }
    return Response(content=pdf_buffer.getvalue(), media_type="application/pdf", headers=headers)

@app.post("/api/patient/{patient_id}/review")
def mark_patient_reviewed(patient_id: str):
    """Marks a patient as human reviewed."""
    predictions_collection.update_one(
        {"patient_id": patient_id},
        {"$set": {"human_reviewed": True}}
    )
    return {"status": "success"}

@app.post("/api/patient/{patient_id}/regenerate-explanation")
def regenerate_patient_explanation(patient_id: str):
    """Force regenerates the AI explanation for a patient."""
    patient = patients_collection.find_one({"_id": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    prediction = predictions_collection.find_one({"patient_id": patient_id}, sort=[("prediction_date", -1)])
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
        
    from backend.llm_service import generate_explanation
    new_exp = generate_explanation(patient, prediction)
    
    from datetime import datetime
    explanations_collection.insert_one({
        "patient_id": patient_id,
        "prediction_id": str(prediction.get("_id", "")),
        "explanation": new_exp,
        "created_at": datetime.utcnow().isoformat()
    })
    
    return {"status": "success", "explanation": new_exp}

@app.post("/api/patient/{patient_id}/mark-review-required")
def mark_patient_review_required(patient_id: str):
    """Manually overrides a patient's risk level to Review Required."""
    predictions_collection.update_one(
        {"patient_id": patient_id},
        {"$set": {"risk_level": "Review Required", "human_reviewed": True}}
    )
    return {"status": "success"}

@app.post("/api/patient/{patient_id}/mark-review-completed")
def mark_patient_review_completed(patient_id: str):
    """Marks a patient's review as completed."""
    predictions_collection.update_one(
        {"patient_id": patient_id},
        {"$set": {"review_status": "Completed", "human_reviewed": True}}
    )
    return {"status": "success"}

def process_zip_background(zip_path: str):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Extracting {zip_path} to {temp_dir}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find the directory containing patients.csv
            target_dir = temp_dir
            for root, dirs, files in os.walk(temp_dir):
                if 'patients.csv' in files:
                    target_dir = root
                    break
                    
            process_synthea_folder(target_dir)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

@app.post("/api/upload-zip")
async def upload_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Handles uploading a ZIP file containing Synthea CSVs for processing."""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")
    
    # Save the file temporarily
    temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
    with os.fdopen(temp_fd, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    # Process in background
    background_tasks.add_task(process_zip_background, temp_path)
    
    return {"message": "File uploaded successfully. Processing will run in the background."}

# Serve Frontend Static Files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
os.makedirs(frontend_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=frontend_path), name="frontend")

@app.get("/")
@app.get("/index.html")
def serve_index():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not built yet. Go to /docs for the API."}

@app.get("/login.html")
def serve_login():
    login_path = os.path.join(frontend_path, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return {"message": "Login page not found."}
