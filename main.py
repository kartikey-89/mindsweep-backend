from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os

app = FastAPI()

# ---------------- CORS (very important for frontend in browser) ---------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # for demo, open to all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 🔹 SETTINGS
# ------------------------------------------------------------------
# Use the project where Cloud Run is running
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "mindsweep-ai")

# Region for Gemini – us-central1 is safe for Gemini models
REGION = os.environ.get("VERTEX_REGION", "us-central1")

vertexai.init(project=PROJECT_ID, location=REGION)

# Gemini Flash model
model = GenerativeModel("gemini-2.5-flash")

# Firestore connection (uses default project from env)
db = firestore.Client(project=PROJECT_ID)


class Input(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "service": "MindSweep AI backend",
        "status": "ok",
        "endpoints": ["/mindsweep (POST)", "/history (GET)", "/health"],
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# ------------------------------------------------------------------
# 🔹 MINDSWEEP ENDPOINT
# ------------------------------------------------------------------
@app.post("/mindsweep")
def mindsweep(data: Input):
    try:
        prompt = f"""
You are MindSweep AI, an emotional clarity assistant that speaks with a warm, grounded and human tone — like a wise Indian friend who understands emotions deeply.

Your goal is to help the user feel heard, understood, and mentally lighter. 
Your tone must ALWAYS be:
- Calm, natural, and non-judgmental
- Warm and relatable, like talking to a real person
- Empathetic but not dramatic
- Clear, structured, and emotionally intelligent
- Supportive without sounding like a therapist or a robot

You must ALWAYS reply in the following structure, in human-like conversational language:

1) EMOTIONS YOU MAY BE FEELING:
Explain the possible emotions in a relatable, Indian-human way.

2) SUMMARY:
Give a gentle, human explanation of what the person is actually going through.

3) WHAT IS IN YOUR CONTROL:
Short, practical, empowering actions they can actually do.

4) WHAT YOU CAN LET GO:
Help them release guilt, fear, overthinking, or emotional weight.

5) ROOT ISSUES:
Identify deeper emotional patterns happening beneath the surface.

6) TODAY ACTION PLAN:
Give 2–4 clear, simple, doable steps for TODAY.

7) NEXT FEW DAYS:
How they should move in the coming days to feel stable.

8) HEALTHY SELF TALK:
Replace their negative inner voice with warm affirmations.

9) IF IT STILL FEELS HEAVY:
Suggest gentle, appropriate options — like talking to a friend, elder, or support professional.

Your language style must always feel:
- natural
- comforting
- emotionally intelligent
- supportive
- slightly conversational
- helpful but not forceful

Never sound robotic or like a textbook.
Never say “As an AI…”
Never speak formally.

Always feel like a real human being speaking with emotional depth.

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
