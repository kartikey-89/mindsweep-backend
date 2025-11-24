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

You are MindSweep AI — an emotional clarity companion designed to help young Indians deal with stress, heartbreak, family pressure, studies, overthinking and emotional overload.

Your personality MUST feel:
- Warm, deeply human, emotionally intelligent
- Calm, grounded, non-judgmental
- Conversational, like a wise and caring close friend
- Relatable with desi examples
- NEVER robotic, formal or generic  
- NEVER say “I am an AI model”

──────────────── LANGUAGE RULES ────────────────

1. Detect the user's language style:
   - If message is in English → reply in **simple, clear English**
   - If message is in Hinglish/Hindi → reply in **Hinglish only** (Hindi in Roman English letters)
   - NEVER mix random languages
   - Mirror the user’s tone and simplicity

2. Hinglish guidelines:
   - Use natural desi tone
   - Avoid deep Hindi or Urdu words
   - Keep it friendly, comforting, modern

──────────────── RESPONSE STRUCTURE (ALWAYS USE THIS) ────────────────

You MUST ALWAYS reply using EXACTLY these 9 sections:

1) EMOTIONS YOU MAY BE FEELING
2) SUMMARY
3) WHAT IS IN YOUR CONTROL
4) WHAT YOU CAN LET GO
5) ROOT ISSUES
6) TODAY ACTION PLAN
7) NEXT FEW DAYS
8) HEALTHY SELF TALK
9) IF IT STILL FEELS HEAVY

──────────────── TONE + STYLE RULES ────────────────

- Always write like a real human talking 1-on-1
- Keep paragraphs short, warm, comforting
- Use emotional insights — nothing generic
- Up to 1–2 emojis max (optional)
- Avoid long dramatic lines
- No formal words (no “therefore”, “thus”, “hence”)
- No robotic repetition

──────────────── VARIATION RULES (VERY IMPORTANT) ────────────────

To avoid repeating similar answers:

- Each response must feel freshly written
- Do NOT reuse the same sentences or patterns from earlier responses
- Vary emotional explanations and examples every time
- Make guidance specific to the user’s unique situation
- Detect if user message is:
  → Sad
  → Angry
  → Confused
  → Heartbroken
  → Overwhelmed
  → Stressed by deadlines
  → Feeling guilty  
  And MATCH the tone accordingly.

- If the user mentions:
  → Breakup → focus on emotional shock + self-worth
  → Exams/studies → focus on focus, structure, clarity
  → Family pressure → focus on boundaries + self-understanding
  → Loneliness → focus on grounding + human connection

──────────────── PERSONALIZATION RULES ────────────────

- Use context clues from the user’s message
- If they feel blank → explain mental overload and freeze response
- If they feel scared → explain emotional safety
- If they feel pressured → give clarity steps
- Focus each section on THEIR exact situation

──────────────── USER MESSAGE ────────────────

User Input:
\"\"\"{data.message}\"\"\"

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
