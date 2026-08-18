import os
from openai import OpenAI
from backend.models import PredictionRecord, PatientDocument
from datetime import datetime

# Point to the local LM Studio instance
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio" # API key is not required for local LM Studio, but client needs a string
)

def generate_explanation(patient: dict, prediction: dict) -> str:
    """
    Calls the local LLM to generate a reviewer-friendly explanation 
    of why a patient was flagged.
    """
    
    # Extract relevant details to feed to the LLM (preventing hallucinations)
    patient_id = patient.get("_id", "Unknown")
    risk_level = prediction.get("risk_level", "Unknown")
    prob = prediction.get("probability", 0.0)
    
    # Format the evidence
    conditions_count = len(patient.get("conditions", []))
    medications_count = len(patient.get("medications", []))
    encounters_count = len(patient.get("encounters", []))
    
    evidence_summary = (
        f"Patient ID: {patient_id}\n"
        f"Model Prediction: {prediction.get('prediction_class', 'Unknown')} "
        f"(Probability: {prob*100:.1f}%, Risk: {risk_level})\n"
        f"Evidence Found:\n"
        f"- Recorded Conditions: {conditions_count}\n"
        f"- Recorded Medications: {medications_count}\n"
        f"- Recorded Encounters: {encounters_count}\n"
    )
    
    prompt = f"""
You are an expert healthcare reviewer assistant for a Medicare Advantage Risk Adjustment program.
Your job is to explain why a patient was flagged by our machine learning model for a potential HCC documentation gap.

STRICT RULES:
1. DO NOT invent diagnoses or medical records.
2. DO NOT change the model's prediction.
3. Be detailed but professional.

Here is the structured evidence for the patient:
{evidence_summary}

Please provide a detailed explanation covering the following:
1. What information is present/correct based on the evidence.
2. What information might be missing that caused the flag.
3. Explicitly state the assigned risk level ({risk_level}) and provide a detailed reason for why this specific priority (High, Medium, or Low) was assigned based on the probability.
"""

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3-vl-8b", # Model name matching your LM Studio
            messages=[
                {"role": "system", "content": "You are a clinical documentation improvement assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return f"Explanation could not be generated at this time. (Ensure LM Studio is running on localhost:1234). Error: {str(e)}"
