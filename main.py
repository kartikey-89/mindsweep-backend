from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
import datetime
import os
import logging
import time

# --------------------------------------------------------
# 🔥 LOGGER SETUP (production-grade)
# --------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("mindsweep")


# --------------------------------------------------------
# 🔥 FASTAPI APP
# --------------------------------------------------------
app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------
# 🔥 GLOBAL ERROR HANDLER (so API never crashes)
# --------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error. Please try again."},
    )


# --------------------------------------------------------
# 🔥 REQUEST LOGGING MIDDLEWARE
# --------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()

    logger.info(f"➡️ Request: {request.method} {request.url}")

    response = await call_next(request)

    duration = round((time.time() - start) * 1000, 2)
    logger.info(f"⬅️ Response: {response.status_code} ({duration} ms)")

    return response


# --------------------------------------------------------
# 🔥 SETTINGS
# --------------------------------------------------------
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "mindsweep-ai")
REGION = os.environ.get("VERTEX_REGION", "us-central1")

vertexai.init(project=PROJECT_ID, location=REGION)

# PRIMARY MODEL
primary_model = GenerativeModel("gemini-2.5-pro")

# FALLBACK MODEL (if above fails)
fallback_model = GenerativeModel("gemini-1.5-flash")


# Firestore connection
db = firestore.Client(project=PROJECT_ID)


class Input(BaseModel):
    message: str


# --------------------------------------------------------
# 🔥 SIMPLE HEALTH CHECK (Backend Only)
# --------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------------
# 🔥 ADVANCED AI HEALTH CHECK
# --------------------------------------------------------
@app.get("/health/ai")
def ai_health():
    try:
        test = primary_model.generate_content("ping")
        return {"ai_status": "working", "model": "gemini-2.5-pro"}
    except:
        try:
            fallback_model.generate_content("ping")
            return {"ai_status": "fallback-active", "model": "gemini-1.5-flash"}
        except Exception as e:
            return {"ai_status": "down", "error": str(e)}


# --------------------------------------------------------
# 🔥 LANGUAGE DETECTION
# --------------------------------------------------------
def detect_language(text: str):
    hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    if hindi_chars > 3:
        return "hindi"

    hinglish_words = [
        "kyu", "kaise", "aisa", "waise", "mujhe", "mera", "tera",
        "kya", "hota", "hogaya", "acha", "accha", "nahi", "nhi",
        "yrr", "bhai", "samjha", "samjh", "matlab", "bol", "kr",
        "dil", "yaar", "scene"
    ]
    if any(w in text.lower() for w in hinglish_words):
        return "hinglish"

    return "english"


# --------------------------------------------------------
# 🔥 MAIN MINDSWEEP ENDPOINT
# --------------------------------------------------------
@app.post("/mindsweep")
def mindsweep(data: Input):

    lang = detect_language(data.message)

    if lang == "hindi":
        language_instruction = "IMPORTANT: User wrote in Hindi. Reply fully in **simple Hindi**."
    elif lang == "hinglish":
        language_instruction = "IMPORTANT: User wrote in Hinglish. Reply fully in **Hinglish (Hindi-English mix)**."
    else:
        language_instruction = "IMPORTANT: User wrote in English. Reply in **simple English**."

    prompt = f"""
{language_instruction}

You are MindSweep AI — an emotional clarity companion...
(KEEP YOUR EXISTING FULL PROMPT HERE EXACTLY AS IT IS)
User Input:
\"\"\"{data.message}\"\"\"
"""

    # ------------ AI CALL WITH FALLBACK ------------
    try:
        result = primary_model.generate_content(prompt)
        clarity = result.text
        model_used = "gemini-2.5-pro"
    except Exception as e:
        logger.error(f"Primary model failed: {str(e)}")
        try:
            result = fallback_model.generate_content(prompt)
            clarity = result.text
            model_used = "gemini-1.5-flash (fallback)"
        except Exception as e2:
            return {"error": f"AI error: {str(e2)}"}

    # ------------ SAVE SAFELY TO FIRESTORE ------------
    try:
        db.collection("mindsweeps").add({
            "message": data.message,
            "clarity": clarity,
            "model_used": model_used,
            "timestamp": datetime.datetime.utcnow()
        })
    except Exception as e:
        logger.error(f"Firestore write error: {str(e)}")
        return {"error": "Firestore error. Try again later."}

    return {"clarity": clarity, "model_used": model_used}


# --------------------------------------------------------
# 🔥 HISTORY ENDPOINT
# --------------------------------------------------------
@app.get("/history")
def history():
    try:
        docs = (
            db.collection("mindsweeps")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(20)
            .stream()
        )

        out = []
        for doc in docs:
            d = doc.to_dict()
            out.append({
                "message": d.get("message", ""),
                "clarity": d.get("clarity", ""),
                "model_used": d.get("model_used", ""),
                "timestamp": d.get("timestamp").isoformat()
            })

        return {"history": out}

    except Exception as e:
        return {"error": f"Firestore read error: {str(e)}"}

