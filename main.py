from fastapi import FastAPI
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os

app = FastAPI()

# ------------------------------------------------------------------
# 🔹 IMPORTANT SETTINGS
# ------------------------------------------------------------------
PROJECT_ID = "mindsweep-ai"        # your project id
REGION = "us-central1"             # Gemini global region (safe & correct)

# Initialize Vertex
vertexai.init(project=PROJECT_ID, location=REGION)

# Gemini Flash 2.5 — Global Model (NO REGION ERRORS)
model = GenerativeModel("gemini-2.5-flash")

# Firestore DB
db = firestore.Client(project=PROJECT_ID)

# Request body structure
class Input(BaseModel):
    message: str


# ------------------------------------------------------------------
# 🔹 MINDSWEEP AI ENDPOINT
# ------------------------------------------------------------------
@app.post("/mindsweep")
def mindsweep(data: Input):
    try:
        prompt = f"""
You are MindSweep AI, an emotional clarity assistant.

Provide the output in EXACTLY this structure:

1) EMOTIONS YOU MAY BE FEELING:
2) SUMMARY:
3) WHAT IS IN YOUR CONTROL:
4) WHAT YOU CAN LET GO:
5) ROOT ISSUES:
6) TODAY ACTION PLAN:
7) NEXT FEW DAYS:
8) HEALTHY SELF TALK:
9) IF IT STILL FEELS HEAVY:

User Input: {data.message}
"""

        result = model.generate_content(prompt)
        clarity = result.text

    except Exception as e:
        return {"error": f"Gemini error: {str(e)}"}

    # Save to Firestore
    try:
        db.collection("mindsweeps").add({
            "message": data.message,
            "clarity": clarity,
            "timestamp": datetime.datetime.utcnow()
        })
    except Exception as e:
        return {"error": f"Firestore error: {str(e)}"}

    return {"clarity": clarity}


# ------------------------------------------------------------------
# 🔹 HISTORY ENDPOINT
# ------------------------------------------------------------------
@app.get("/history")
def get_history():
    try:
        entries = (
            db.collection("mindsweeps")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(20)
            .stream()
        )

        history_list = []
        for e in entries:
            item = e.to_dict()
            history_list.append({
                "message": item.get("message", ""),
                "clarity": item.get("clarity", ""),
                "timestamp": item.get("timestamp").isoformat()
                    if item.get("timestamp")
                    else ""
            })

        return {"history": history_list}

    except Exception as e:
        return {"error": f"Firestore read error: {str(e)}"}
