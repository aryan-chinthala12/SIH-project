from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import uuid

app = Flask(__name__)
CORS(app)  # allow frontend on localhost to connect

# ---------------- Sentiment lexicon ----------------
POS = {
    "good": 1, "great": 2, "happy": 2, "love": 2, "liked": 1,
    "awesome": 2, "helpful": 1, "ok": 1, "fine": 1, "better": 1
}
NEG = {
    "sad": -1, "bad": -1, "terrible": -2, "angry": -2, "hate": -2,
    "upset": -1, "anxious": -1, "worried": -1, "stressed": -1, "depressed": -2,
    "tired": -1, "pain": -1, "sick": -1, "not": -0.2
}

def analyze_sentiment(text):
    text = text.lower()
    tokens = re.findall(r"\w+", text)
    score = 0.0
    for t in tokens:
        if t in POS: score += POS[t]
        if t in NEG: score += NEG[t]

    if score > 1:
        label = "positive"
    elif score < -1:
        label = "negative"
    else:
        label = "neutral"
    return {"score": score, "label": label}

# ---------------- Rule-based intents ----------------
INTENT_PATTERNS = [
    ("greeting", r"\b(hi|hello|hey|good morning|good evening)\b"),
    ("bye", r"\b(bye|goodbye|see you|cya)\b"),
    ("thanks", r"\b(thank|thanks|thx)\b"),
    ("help", r"\b(help|support|assist|need)\b"),
    ("symptom", r"\b(fever|cough|headache|nausea|pain|sick|ill)\b"),
]

RESPONSES = {
    "greeting": "Hey! I'm your assistant. How can I help today?",
    "bye": "Take care! Come back anytime.",
    "thanks": "You're welcome! 😊",
    "help": "Tell me briefly what's happening — if it's an emergency, please reach local services.",
    "symptom": "Sorry you're not feeling well. How long and how severe (mild/moderate/severe)?",
    "fallback": "I didn’t get that — can you rephrase?",
}

def detect_intent(text):
    text = text.lower()
    for intent, patt in INTENT_PATTERNS:
        if re.search(patt, text):
            return intent
    return None

# ---------------- In-memory session store ----------------
SESSIONS = {}

# ---------------- Questionnaire ----------------
QUESTIONNAIRE = [
    {"id": "q1", "text": "Over the last 2 weeks, how often have you felt down, depressed, or hopeless?", "max": 3},
    {"id": "q2", "text": "Over the last 2 weeks, how often have you had trouble sleeping?", "max": 3},
    {"id": "q3", "text": "Over the last 2 weeks, how often have you felt little interest in doing things?", "max": 3},
    {"id": "q4", "text": "Over the last 2 weeks, how often have you felt anxious or nervous?", "max": 3},
    {"id": "q5", "text": "Over the last 2 weeks, how often have you had difficulty concentrating?", "max": 3},
]

def interpret_score(score, max_score):
    pct = score / max_score
    if pct >= 0.8:
        return {"category": "High", "advice": "Please consider seeking professional help soon."}
    elif pct >= 0.5:
        return {"category": "Moderate", "advice": "Monitor and consider talking to a counselor."}
    else:
        return {"category": "Low", "advice": "Symptoms are low — keep self-care and tracking."}

# ---------------- API Routes ----------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    text = data.get("message", "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    if session_id not in SESSIONS:
        SESSIONS[session_id] = []

    intent = detect_intent(text)
    sentiment = analyze_sentiment(text)

    if intent:
        reply = RESPONSES.get(intent, RESPONSES["fallback"])
    else:
        if sentiment["label"] == "negative":
            reply = "I'm sorry you're feeling that way. Want breathing tips, a distraction, or to fill a questionnaire?"
        elif sentiment["label"] == "positive":
            reply = "That's good to hear! Anything else you'd like help with?"
        else:
            reply = RESPONSES["fallback"]

    SESSIONS[session_id].append({"from": "user", "text": text})
    SESSIONS[session_id].append({"from": "bot", "text": reply})

    return jsonify({"reply": reply, "intent": intent, "sentiment": sentiment, "session_id": session_id})

@app.route("/questionnaire", methods=["GET"])
def get_questions():
    return jsonify({"questions": QUESTIONNAIRE})

@app.route("/questionnaire", methods=["POST"])
def submit_questions():
    data = request.json
    answers = data.get("answers", {})
    session_id = data.get("session_id")

    score = 0
    max_score = sum(q["max"] for q in QUESTIONNAIRE)

    for q in QUESTIONNAIRE:
        val = int(answers.get(q["id"], 0))
        if val < 0: val = 0
        if val > q["max"]: val = q["max"]
        score += val

    result = interpret_score(score, max_score)

    if session_id:
        SESSIONS.setdefault(session_id, []).append({"from": "system", "questionnaire_score": score})

    return jsonify({
        "score": score,
        "max_score": max_score,
        "category": result["category"],
        "advice": result["advice"],
        "session_id": session_id
    })

@app.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    return jsonify({"session": SESSIONS.get(session_id, [])})

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
