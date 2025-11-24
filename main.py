from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- SETTINGS ----------------
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "mindsweep-ai")
REGION = os.environ.get("VERTEX_REGION", "us-central1")

vertexai.init(project=PROJECT_ID, location=REGION)

model = GenerativeModel("gemini-2.5-pro")

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


# ============================================================
# 🔥 LANGUAGE DETECTION (English / Hindi / Hinglish)
# ============================================================
def detect_language(text: str):

    # detect Hindi script
    hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    if hindi_chars > 3:
        return "hindi"

    # detect hinglish patterns
    hinglish_words = [
        "kyu", "kaise", "aisa", "waise", "mujhe", "mera", "tera",
        "kya", "hota", "hogaya", "acha", "accha", "nahi", "nhi",
        "yrr", "bhai", "samjha", "samjh", "matlab", "bol", "kr",
        "mera", "tere", "dil", "yaar"
    ]

    if any(w in text.lower() for w in hinglish_words):
        return "hinglish"

    return "english"


# ============================================================
# 🔥 MINDSWEEP ENDPOINT
# ============================================================
@app.post("/mindsweep")
def mindsweep(data: Input):

    # Detect language first
    lang = detect_language(data.message)

    if lang == "hindi":
        language_instruction = (
            "IMPORTANT: User wrote in Hindi. Respond fully in **simple Hindi**, "
            "warm tone, natural emotional language."
        )
    elif lang == "hinglish":
        language_instruction = (
            "IMPORTANT: User wrote in Hinglish. Respond fully in **Hinglish** "
            "(Hindi + English mix) with natural desi conversational tone."
        )
    else:
        language_instruction = (
            "IMPORTANT: User wrote in English. Respond in **simple, warm English**."
        )

    # ---------------- PROMPT WITH LANGUAGE INSTRUCTION ----------------
    prompt = f"""
{language_instruction}

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

You MUST ALWAYS reply in this **exact 9-section structure**:

1) EMOTIONS YOU MAY BE FEELING  
2) SUMMARY  
3) WHAT IS IN YOUR CONTROL  
4) WHAT YOU CAN LET GO  
5) ROOT ISSUES  
6) TODAY ACTION PLAN  
7) NEXT FEW DAYS  
8) HEALTHY SELF TALK  
9) IF IT STILL FEELS HEAVY  

STYLE RULES:  
- Always sound human.  
- Never sound like an AI.  
- No generic advice.  
- No long paragraphs.  
- No dramatic tone.  
- 1–2 natural emojis max (optional).  
- Emotionally insightful and calming.  

User Input: {data.message}
"""

    # ------------------- AI CALL --------------------
    try:
        result = model.generate_content(prompt)
        clarity = result.text
    except Exception as e:
        return {"error": f"Gemini error: {str(e)}"}

    # ------------------- FIRESTORE SAVE --------------------
    try:
        db.collection("mindsweeps").add({
            "message": data.message,
            "clarity": clarity,
            "timestamp": datetime.datetime.utcnow()
        })
    except Exception as e:
        return {"error": f"Firestore error: {str(e)}"}

    return {"clarity": clarity}


# ============================================================
# 🔥 HISTORY ENDPOINT
# ============================================================
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
