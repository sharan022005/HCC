import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)

# Database Name
db = client["hcc_gap_detection"]

# Collections
patients_collection = db["patients"]
predictions_collection = db["predictions"]
explanations_collection = db["llm_explanations"]
admins_collection = db["admins"]

def get_db():
    return db
