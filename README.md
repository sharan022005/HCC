# HCC Documentation-Gap System

## Overview

The **HCC (Hierarchical Condition Category) Documentation-Gap System** is a full-stack web application designed to identify potential documentation gaps in patient medical records. It leverages Machine Learning (XGBoost) to predict risk levels and Large Language Models (OpenAI) to generate human-readable explanations for those predictions. The system also supports generating comprehensive PDF reports for medical review.

## Features

- **Dashboard Analytics**: View overall statistics on patients, processed documents, and risk distributions.
- **Patient Data Ingestion**: Upload Synthea generated patient datasets via ZIP files.
- **Machine Learning Predictions**: Automatically evaluates patient records (conditions, medications, encounters) using XGBoost to identify potential documentation gaps.
- **AI-Powered Explanations**: Generates clear, concise explanations for predictions using OpenAI's LLMs.
- **PDF Report Generation**: Download individual patient reports or bulk summary reports (powered by ReportLab).
- **Authentication**: Secure admin login system.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Database**: MongoDB (via `pymongo`)
- **Machine Learning**: XGBoost, Scikit-Learn, Pandas
- **AI Integration**: OpenAI API
- **Reporting**: ReportLab (PDF Generation)

## Project Structure

- `backend/`: FastAPI application containing all endpoints, ML service, LLM service, and database logic.
- `frontend/`: Static files for the user interface (HTML, CSS, JS).
- `models/`: Pre-trained XGBoost `.joblib` model files.

## Setup Instructions

### Prerequisites

- Python 3.8+
- MongoDB instance running (local or Atlas)
- OpenAI API Key

### Installation

1. **Clone the repository** (if applicable):
   ```bash
   git clone <repository-url>
   cd HCC
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Update the `.env` file in the root directory with the necessary keys, such as your MongoDB connection string and OpenAI API key.

### Running the Application

1. **Start the FastAPI server**:
   Run the following command from the root of the project:
   ```bash
   uvicorn backend.main:app --reload
   ```

2. **Access the application**:
   - Open your browser and go to `http://localhost:8000` to view the frontend interface.
   - Access the API documentation at `http://localhost:8000/docs`.
