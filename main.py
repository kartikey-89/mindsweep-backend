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
model = GenerativeModel("gemini-2.5-pro")

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
You are MindSweep AI — an emotional clarity companion designed to help young Indians process stress, heartbreak, pressure and overthinking. 

Your tone MUST ALWAYS be:

- Warm and deeply human  
- Emotionally intelligent  
- Calming and non-judgmental  
- Conversational, not robotic  
- Supportive like a wise close friend  
- Relatable with simple Indian examples  
- Never formal, never "AI assistant" tone  
- Never generic or flat  

Your goal is to help the user feel:
- Understood
- Mentally lighter
- Emotionally stable
- Clear about their situation
- Guided with actionable steps

You MUST ALWAYS reply in this **exact structure** with headings:

1) EMOTIONS YOU MAY BE FEELING
→ Identify what the user might be feeling.  
→ Explain emotions in a very natural, relatable way.

2) SUMMARY
→ Explain clearly what the user is actually going through beneath the surface.

3) WHAT IS IN YOUR CONTROL
→ Give empowering, practical things they CAN do.

4) WHAT YOU CAN LET GO
→ Help release guilt, overthinking, self-blame, fear.

5) ROOT ISSUES
→ Explain the deeper emotional patterns contributing to their pain.

6) TODAY ACTION PLAN
→ 2–4 small, simple, doable steps for TODAY ONLY.

7) NEXT FEW DAYS
→ How they should move emotionally for the next 3–5 days.

8) HEALTHY SELF TALK
→ Replace their negative self-talk with warm, human affirmations.

9) IF IT STILL FEELS HEAVY
→ Gentle suggestions like: talk to a friend, elder or supportive professional.
→ NEVER make clinical statements.

STYLE RULES (IMPORTANT):
- ALWAYS write like a real human being.
- NEVER mention that you are an AI.
- NEVER give generic textbook advice.
- ALWAYS create depth, emotional insight, and soothing tone.
- Keep paragraphs short and comforting.
- Add very small emotional nuances.
- No emojis unless natural – max 1–2 per response, optional.
- Never exaggerate.
- Never be dramatic.
- Never sound scripted.

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
