import os
import pandas as pd
from pymongo import MongoClient, UpdateOne
from backend.database import patients_collection
from backend.ml_service import predict_documentation_gap_batch
import argparse

def process_synthea_folder(folder_path: str):
    """
    Reads Synthea CSVs from a folder, merges them on PATIENT ID,
    inserts into MongoDB, and runs predictions.
    """
    print(f"Reading from {folder_path}...")
    
    # Check if patients.csv exists
    patients_file = os.path.join(folder_path, "patients.csv")
    if not os.path.exists(patients_file):
        print("Error: patients.csv not found in folder.")
        return

    # Read patients
    print("Loading patients...")
    try:
        df_patients = pd.read_csv(patients_file, on_bad_lines='skip')
    except Exception as e:
        print(f"Failed to read patients.csv: {e}")
        return
    
    # Read supporting files
    files = {
        "conditions": os.path.join(folder_path, "conditions.csv"),
        "encounters": os.path.join(folder_path, "encounters.csv"),
        "medications": os.path.join(folder_path, "medications.csv"),
        "careplans": os.path.join(folder_path, "careplans.csv"),
        "procedures": os.path.join(folder_path, "procedures.csv")
    }
    
    data_dicts = {k: {} for k in files.keys()}
    
    for key, path in files.items():
        if os.path.exists(path):
            print(f"Loading {key}...")
            # For massive files like observations.csv, use chunking.
            # Here we just read the standard supporting files.
            try:
                df_temp = pd.read_csv(path, on_bad_lines='skip')
                # Group by PATIENT to easily attach to patient documents
                grouped = df_temp.groupby('PATIENT')
                for pid, group in grouped:
                    data_dicts[key][pid] = group.to_dict('records')
            except Exception as e:
                print(f"Skipping {key} due to error: {e}")

    print("Building patient documents and running ML predictions...")
    
    BATCH_SIZE = 2500
    batch_docs = []
    bulk_ops = []
    total_processed = 0
    
    # Iterate over each patient
    for idx, row in df_patients.iterrows():
        # Handle variations in column names for the patient ID
        pid = row.get('Id', row.get('ID', row.get('id', row.get('PATIENT'))))
        if pd.isna(pid):
            continue
        try:
            birthdate = pd.to_datetime(row.get('BIRTHDATE', '1900-01-01'))
            deathdate = pd.to_datetime(row.get('DEATHDATE', pd.Timestamp.now()))
            age = int((deathdate - birthdate).days / 365.25)
        except:
            age = 0
            
        patient_doc = {
            "_id": pid,
            "demographics": {
                "age": age,
                "gender": row.get("GENDER", "U"),
                "race": row.get("RACE", ""),
                "ethnicity": row.get("ETHNICITY", "")
            },
            "conditions": data_dicts["conditions"].get(pid, []),
            "encounters": data_dicts["encounters"].get(pid, []),
            "medications": data_dicts["medications"].get(pid, []),
            "careplans": data_dicts["careplans"].get(pid, []),
            "procedures": data_dicts["procedures"].get(pid, [])
        }
        
        batch_docs.append(patient_doc)
        bulk_ops.append(
            UpdateOne({"_id": pid}, {"$set": patient_doc}, upsert=True)
        )
        
        total_processed += 1
        
        # Process in batches
        if len(batch_docs) >= BATCH_SIZE:
            # 1. Bulk write patients
            patients_collection.bulk_write(bulk_ops)
            # 2. Batch predict and bulk write predictions
            predict_documentation_gap_batch(batch_docs, pipeline_type="synthea")
            
            print(f"Processed {total_processed} patients...")
            
            # Reset batches
            batch_docs = []
            bulk_ops = []
            
    if batch_docs:
        patients_collection.bulk_write(bulk_ops)
        predict_documentation_gap_batch(batch_docs, pipeline_type="synthea")
        print(f"Processed {total_processed} patients...")
            
    print("Done! Data ingested and predictions generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Synthea CSVs into MongoDB")
    parser.add_argument("folder", help="Path to the folder containing Synthea CSVs")
    args = parser.parse_args()
    
    process_synthea_folder(args.folder)
