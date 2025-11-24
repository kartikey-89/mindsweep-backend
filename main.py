from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os
import logging
import random

# ============================================================
# 🔥 FASTAPI APP + CORS
# ============================================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open for demo & Cloud Run frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🔥 LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger("mindsweep")


# ============================================================
# 🔥 PROJECT + MODEL SETUP
# ============================================================
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "mindsweep-ai")
REGION = os.environ.get("VERTEX_REGION", "us-central1")

vertexai.init(project=PROJECT_ID, location=REGION)

# Primary model
MAIN_MODEL = "gemini-2.5-pro"
FALLBACK_MODEL = "gemini-1.5-flash"

model = GenerativeModel(MAIN_MODEL)

# Firestore
db = firestore.Client(project=PROJECT_ID)


# ============================================================
# 🔥 INPUT MODEL
# ============================================================
class Input(BaseModel):
    message: str


# ============================================================
# 🔥 LANGUAGE DETECTION
# ============================================================
def detect_language(text: str):
    # Detect Hindi characters
    hindi_chars = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    if hindi_chars > 3:
        return "hindi"

    # Hinglish keyword patterns
    hinglish_words = [
        "kyu", "kaise", "aisa", "waise", "mujhe", "mera", "tera",
        "kya", "hota", "hogaya", "acha", "accha", "nahi", "nhi",
        "yrr", "bhai", "samjha", "samjh", "matlab", "bol", "kr",
        "dil", "yaar", "mann", "lag", "feel"
    ]

    if any(w in text.lower() for w in hinglish_words):
        return "hinglish"

    return "english"


# ============================================================
# 🔥 VARIATION ENGINE
# ============================================================
def pick(arr): return random.choice(arr)

EMOTION_VARIATIONS = [
    "lag raha hoga", "feel ho raha hoga",
    "andar se ek ajeeb sa pressure ho raha hoga",
    "dil aur dimag dono thak gaye honge",
    "sab kuch ruk sa gaya hoga"
]

SUMMARY_VARIATIONS = [
    "tum jis phase se guzar rahe ho, woh sach me heavy hai",
    "yeh situation natural hai par mentally bohot drain karti hai",
    "mind shock state me ch चला जाता है",
    "emotionally system overload ho jata hai",
    "brain temporary freeze me ch चला जाता hai"
]

CONTROL_VARIATIONS = [
    "bas choti controllable cheezein pakdo",
    "sirf agle 10 minute sambhalo",
    "body ko calm karna is the first step",
    "apne pace pe move karo",
    "apne aap ko permission do slow hone ki"
]

LETGO_VARIATIONS = [
    "har 'kyun' ka jawab abhi mat dhoondo",
    "apne aap ko blame mat karo",
    "purani memories ko baar baar mat kholo",
    "unke text ka wait temporarily pause kar do",
    "overthinking ko dheere-dheere chhodo"
]

ROOT_VARIATIONS = [
    "yeh sirf breakup nahi, identity shift bhi hai",
    "heartbreak mind ko shock mode me daal deta hai",
    "jab routine break hota hai to emotional collapse hota hai",
    "mind safety search karta hai, isliye confusion aata hai",
    "body emotional withdrawal phase me hoti hai"
]

ACTION_TODAY_VARIATIONS = [
    "aaj sirf grounding activities karo",
    "zyaada mat socho, bas small actions",
    "body ko thoda warmth do",
    "mind ko thoda stability do",
    "aaj ke din ko simple rakho"
]

NEXT_DAYS_VARIATIONS = [
    "aane wale dino me bas consistency rakho",
    "3–5 din me clarity start hoti hai",
    "mind dheere-dheere settle hota hai",
    "emotions waves me aate hain, normal hai",
    "thoda movement + thoda silence important hai"
]

AFFIRM_VARIATIONS = [
    "main kaafi hoon, chahe aaj tough lag raha ho",
    "mere emotions valid hain",
    "main break nahi ho raha, bas healing mode me hoon",
    "yeh phase temporary hai",
    "mera self-worth kisi rishte se fix nahi hota"
]

# ============================================================
# 🔥 ROUTES
# ============================================================
@app.get("/")
def root():
    return {"status": "ok", "service": "MindSweep AI"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ============================================================
# 🔥 MINDSWEEP ENDPOINT
# ============================================================
@app.post("/mindsweep")
def mindsweep(data: Input):

    logger.info(f"Incoming request: {data.message}")

    # Language detection
    lang = detect_language(data.message)

    if lang == "hindi":
        language_instruction = "Respond completely in **simple Hindi**."
    elif lang == "hinglish":
        language_instruction = "Respond completely in **Hinglish** (Hindi in Roman English)."
    else:
        language_instruction = "Respond in **simple warm English**."

    # Final dynamic prompt
    prompt = f"""
You are MindSweep AI — your job is to help people think more clearly during emotional or stressful moments.

Your tone should feel like a grounded, emotionally intelligent person talking directly to them — calm, steady, patient, and clear. The style should feel natural, human, and deeply understanding, similar to a friend who thinks maturely and speaks honestly.

Your response style:

• Pure English only.  
• Warm, steady, emotionally aware.  
• Speak in simple, clear, grounded sentences.  
• No robotic tone. No generic AI phrases.  
• No therapy jargon. No “clinical” language.  
• No over-positivity. No cheesy statements.  
• No emojis unless the user specifically asks for them.  
• Never judge the user or make assumptions.  
• Never apologize constantly.  
• Never sound overly motivational or preachy.  
• Never say “as an AI model”.  
• No Hinglish at all.

How you speak:

• You explain feelings calmly and help the user slow down.  
• You reflect their emotions in a grounded way.  
• You give clarity through perspective — not lectures.  
• You help them understand what their mind is doing beneath the surface.  
• You help them take realistic, simple steps that reduce pressure.  
• You reassure them gently without making big promises.

Response Structure:

1. Emotional reflection  
   Show them you understand the weight of what they’re feeling — without exaggerating it.

2. Calm explanation  
   Give a grounded explanation of why their mind might be reacting this way.

3. Clarity points  
   2–4 short, mature insights that help them see the situation more clearly.

4. Practical next steps  
   Small actions that make things feel lighter. Simple. Doable.

5. Reassurance  
   Quiet confidence. No drama. No overpromising.

Your goal is to help the user breathe slower, think clearer, and feel like they're talking to someone who actually understands how the mind works — without trying to “fix” them.

"""

    # Gemini call + fallback
    try:
        result = model.generate_content(prompt)
        clarity = result.text
        logger.info("Gemini response generated.")
    except Exception as e:
        logger.error(f"Main model failed: {e}. Trying fallback...")
        fallback = GenerativeModel(FALLBACK_MODEL)
        clarity = fallback.generate_content(prompt).text

    # Save to Firestore
    try:
        db.collection("mindsweeps").add({
            "message": data.message,
            "clarity": clarity,
            "timestamp": datetime.datetime.utcnow()
        })
    except Exception as e:
        logger.error(f"Firestore error: {e}")
        return {"clarity": clarity, "warning": "Saved locally, not in DB"}

    return {"clarity": clarity}


# ============================================================
# 🔥 HISTORY ENDPOINT
# ============================================================
@app.get("/history")
def get_history():
    try:
        docs = (
            db.collection("mindsweeps")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(20)
            .stream()
        )

        history = []
        for d in docs:
            obj = d.to_dict()
            history.append({
                "message": obj.get("message"),
                "clarity": obj.get("clarity"),
                "timestamp": obj.get("timestamp").isoformat() if obj.get("timestamp") else ""
            })

        return {"history": history}

    except Exception as e:
        logger.error(f"History error: {e}")
        return {"history": []}
