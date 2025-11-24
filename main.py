from fastapi import FastAPI
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime

app = FastAPI()

# ✅ Correct project + region
PROJECT_ID = "mindsweep-ai"
REGION = "asia-south1"   # Mumbai region (same as Firestore)

# ✅ Init Vertex AI in Mumbai region
vertexai.init(project=PROJECT_ID, location=REGION)

# ✅ Use latest active Gemini model
model = GenerativeModel("gemini-2.5-flash")
# Agar kabhi issue aaye to ye bhi try kar sakte ho:
# model = GenerativeModel("gemini-2.5-flash-lite")

db = firestore.Client(project=PROJECT_ID)

class Input(BaseModel):
    message: str

@app.post("/mindsweep")
def mindsweep(data: Input):
    try:
        prompt = f"""
        You are MindSweep AI, an emotional clarity assistant.
        Provide structured clarity in 9 clear sections.

        1) EMOTIONS YOU MAY BE FEELING:
        2) SUMMARY:
        3) WHAT IS IN YOUR CONTROL:
        4) WHAT YOU CAN LET GO:
        5) ROOT ISSUES:
        6) TODAY ACTION PLAN:
        7) NEXT FEW DAYS:
        8) HEALTHY SELF TALK:
        9) IF IT STILL FEELS HEAVY:

        User: {data.message}
        """

        result = model.generate_content(prompt)
        clarity = result.text

    except Exception as e:
        return {"error": f"Gemini error: {str(e)}"}

    try:
        db.collection("mindsweeps").add({
            "message": data.message,
            "clarity": clarity,
            "timestamp": datetime.datetime.utcnow()
        })
    except Exception as e:
        return {"error": f"Firestore error: {str(e)}"}

    return {"clarity": clarity}
