from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SyntheaDemographics(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    race: Optional[str] = None
    ethnicity: Optional[str] = None

class PatientDocument(BaseModel):
    patient_id: str = Field(alias="_id")
    demographics: SyntheaDemographics
    conditions: List[Dict[str, Any]] = []
    encounters: List[Dict[str, Any]] = []
    medications: List[Dict[str, Any]] = []
    careplans: List[Dict[str, Any]] = []
    procedures: List[Dict[str, Any]] = []

class PredictionRecord(BaseModel):
    patient_id: str
    model_name: str
    prediction_class: str # e.g., "Potential Gap" or "Supported"
    probability: float
    risk_level: str
    prediction_date: str

class LLMExplanation(BaseModel):
    patient_id: str
    explanation: str
    created_at: str
