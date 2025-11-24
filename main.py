from fastapi import FastAPI
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os

app = FastAPI()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = "asia-south1"

vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel("gemini-1.5-flash")

db = firestore.Client()

class Input(BaseModel):
    message: str

@app.post("/mindsweep")
def mindsweep(data: Input):
    prompt = f"""
    You are MindSweep AI, an emotional clarity assistant.
    Provide calm, structured guidance.

    Respond in this structure:
    1) EMOTIONS YOU MAY BE FEELING:
    2) SUMMARY:
    3) WHAT IS IN YOUR CONTROL:
    4) WHAT YOU CAN LET GO:
    5) ROOT ISSUES:
    6) TODAY ACTION PLAN:
    7) NEXT FEW DAYS:
    8) HEALTHY SELF TALK:
    9) IF FEELS HEAVY:

    User message:
    {data.message}
    """

    response = model.generate_content(prompt)
    clarity = response.text

    db.collection("mindsweeps").add({
        "message": data.message,
        "clarity": clarity,
        "timestamp": datetime.datetime.utcnow()
    })

    return {"clarity": clarity}
