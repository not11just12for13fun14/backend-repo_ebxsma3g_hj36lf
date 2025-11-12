import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database import create_document, get_documents, db
from bson import ObjectId

app = FastAPI(title="MinSplit API", description="Debate between Emotional and Logical agents to help decisions")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DebateRequest(BaseModel):
    situation: str


# ----------------------------- Utility ---------------------------------

def serialize_doc(doc: dict):
    if not doc:
        return doc
    d = dict(doc)
    _id = d.get("_id")
    if isinstance(_id, ObjectId):
        d["id"] = str(_id)
        del d["_id"]
    # convert datetimes to iso
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    # nested messages
    if isinstance(d.get("messages"), list):
        for m in d["messages"]:
            for mk, mv in list(m.items()):
                if hasattr(mv, "isoformat"):
                    m[mk] = mv.isoformat()
    return d


def extract_tags(situation: str) -> List[str]:
    s = situation.lower()
    tags = []
    keywords = {
        "career": ["job", "career", "offer", "promotion", "switch", "role"],
        "finance": ["salary", "money", "budget", "investment", "loan", "debt", "buy", "rent"],
        "relationships": ["relationship", "partner", "friend", "family", "marriage", "dating"],
        "health": ["health", "exercise", "diet", "sleep", "stress", "burnout"],
        "education": ["college", "course", "study", "studying", "degree", "learn", "bootcamp", "exam", "test", "math"],
        "relocation": ["move", "relocate", "city", "country"],
        "purchase": ["buy", "purchase", "upgrade", "phone", "car", "house"],
        "hobby": ["cricket", "football", "soccer", "game", "gaming", "sport", "sports", "music"]
    }
    for tag, kws in keywords.items():
        if any(kw in s for kw in kws):
            tags.append(tag)
    if not tags:
        tags.append("general")
    return tags


def key_phrases(situation: str) -> List[str]:
    s = situation.strip()
    # naive phrase extraction: split by punctuation, pick meaningful chunks
    parts = []
    for chunk in s.replace("?", ".").replace("!", ".").split("."):
        c = chunk.strip()
        if 4 <= len(c) <= 140:
            parts.append(c)
    if not parts and s:
        parts = [s]
    return parts[:4]


def sentiment_hint(situation: str) -> str:
    s = situation.lower()
    positive = any(w in s for w in ["excited", "happy", "love", "great", "amazing", "dream", "like"])
    negative = any(w in s for w in ["scared", "anxious", "worried", "stress", "burnout", "bad", "risky", "don't feel like", "bored", "tired"])
    if positive and not negative:
        return "leans positive"
    if negative and not positive:
        return "leans cautious"
    return "mixed"


def generate_debate(situation: str):
    s = situation.strip()
    tags = extract_tags(s)
    phrases = key_phrases(s)
    tone = sentiment_hint(s)

    # Specialized tailoring for exams vs hobbies (e.g., cricket)
    is_exam = any(t in tags for t in ["education"]) and any(x in s.lower() for x in ["exam", "test", "math"])
    likes_cricket = "cricket" in s.lower()

    # Openers tailored by tone
    if is_exam:
        emo_open = (
            "You're torn, and that's human: the exam feels heavy and cricket feels alive. Let's protect your future self without killing your present joy."
        )
        logic_open = (
            "There's one night left. We need a plan that maximizes marginal score gain per minute and still respects recovery."
        )
    else:
        emo_open = (
            f"I can feel how this {tone} decision sits with you. Let's honor what your day-to-day will feel like, not just the headline outcome."
        )
        logic_open = (
            "Let's turn this into a clear decision model: objectives, constraints, options, and reversible next actions."
        )

    # Dynamic points
    emo_points: List[str] = []
    log_points: List[str] = []

    if is_exam:
        emo_points.extend([
            "Name the feeling right now: resistance, anxiety, or boredom? Naming reduces its grip. Give it compassion, not shame.",
            "Imagine tomorrow morning you: calm, proud, and not panicked. What minimum tonight gives you that feeling?",
        ])
        log_points.extend([
            "Identify high-yield topics for a math exam: formulas, typical problem types, and error patterns. These dominate last-day ROI.",
            "Do a 90-minute focus block: 3 x 25-minute Pomodoro on weak areas + 5-minute reviews. Then a 15-minute quick quiz to verify retention.",
        ])
        if likes_cricket:
            emo_points.append("Cricket energizes you. Use it as a reward, not an escape: a short session after the focus block keeps motivation clean.")
            log_points.append("If-Then plan: If you finish the 90-minute block and one quiz, then play 30 minutes of cricket. Put gear out of sight until then.")
        # Incorporate user phrases directly
        for p in phrases:
            emo_points.append(f"When you think about '{p}', what value matters most—competence, joy, or balance? Choose actions that respect that value.")
            log_points.append(f"For '{p}', write 3 must-know items. Test yourself once. If recall < 80%, repeat once, else move on.")
        # Self-checks
        emo_self = "I might be overprotecting comfort. One short discomfort now can protect tomorrow's peace."
        log_self = "I might be ignoring motivation. The plan must be doable—short, clear wins beat ideal schedules."
        # Tailored action
        action = (
            "Tonight: 90 minutes focused practice on key math topics (formulas, typical problems), then 30 minutes of cricket as a reward. Hydrate, prep bag, sleep >= 7 hours."
        )
    else:
        for p in phrases:
            emo_points.append(
                f"When you picture '{p}', what emotion shows up first—ease, excitement, or tension? Follow the one that sustains your energy."
            )
            log_points.append(
                f"For '{p}', list two options. Score each 1–5 on impact, effort, risk, and reversibility. Prefer the higher expected value with low irreversible risk."
            )
        # Generic scaffolding
        emo_points.append("Protect sleep, relationships, and identity—these are compounding assets.")
        log_points.append("Design a 7–14 day reversible test to gather evidence before a full commit.")
        emo_self = (
            "I might be romanticizing the ideal day. Let's ground this by noting one concrete discomfort you're willing to accept."
        )
        log_self = (
            "I might be over-optimizing metrics. Let's not ignore motivation and meaning—the plan must be energizing to be sustainable."
        )
        # Action tailored by tags
        action = "Run a small, time-boxed experiment and measure real signals."
        if "finance" in tags:
            action = "Create a 30–60–90 budget, cap downside, and trial the change with strict guardrails."
        if "career" in tags:
            action = "Define three success metrics (learning, compensation, impact) and do a 2-week shadow or pilot."
        if "relationships" in tags:
            action = "Schedule a candid conversation, co-create boundaries, and review in 2 weeks."
        if "health" in tags:
            action = "Adopt a minimal routine (sleep, meals, 20‑min walk) and review mood and energy after 10 days."

    messages: List[dict] = []
    turn = 1
    messages.append({"role": "user", "content": s, "turn": 0})
    messages.append({"role": "emotional", "content": emo_open, "turn": turn}); turn += 1
    messages.append({"role": "logical", "content": logic_open, "turn": turn}); turn += 1

    for ep, lp in zip(emo_points, log_points):
        messages.append({"role": "emotional", "content": ep, "turn": turn}); turn += 1
        messages.append({"role": "logical", "content": lp, "turn": turn}); turn += 1

    messages.append({"role": "emotional", "content": emo_self, "turn": turn}); turn += 1
    messages.append({"role": "logical", "content": log_self, "turn": turn}); turn += 1

    final_decision = (
        "Balanced Decision: choose the path that preserves mental health and values while maximizing reversible upside. "
        + action
    )
    messages.append({"role": "summary", "content": final_decision, "turn": turn}); turn += 1

    return messages, final_decision, tags


# ----------------------------- Routes ---------------------------------

@app.get("/")
def read_root():
    return {"message": "MinSplit API is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from MinSplit backend!"}

@app.post("/api/debate")
def create_debate(req: DebateRequest):
    if not req.situation or not req.situation.strip():
        raise HTTPException(status_code=400, detail="Situation is required")

    messages, final_decision, tags = generate_debate(req.situation)

    conv = {
        "situation": req.situation.strip(),
        "messages": messages,
        "final_decision": final_decision,
        "tags": tags,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    conv_id = create_document("conversation", conv)

    return {
        "conversation_id": conv_id,
        "situation": conv["situation"],
        "messages": messages,
        "final_decision": final_decision,
        "tags": tags,
    }


@app.get("/api/conversations")
def list_conversations(limit: int = 50):
    docs = get_documents("conversation", {}, limit=limit)
    # Sort newest first if possible
    try:
        docs = sorted(docs, key=lambda d: d.get("created_at", datetime.min), reverse=True)
    except Exception:
        pass
    # return only lightweight fields
    out = []
    for d in docs:
        item = {
            "id": str(d.get("_id")),
            "situation": d.get("situation"),
            "final_decision": d.get("final_decision"),
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
            "tags": d.get("tags", []),
        }
        out.append(item)
    return {"items": out}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    try:
        oid = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation id")

    doc = db["conversation"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize_doc(doc)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    try:
        oid = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation id")

    res = db["conversation"].delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "id": conversation_id}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
