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
        "education": ["college", "course", "study", "degree", "learn", "bootcamp"],
        "relocation": ["move", "relocate", "city", "country"],
        "purchase": ["buy", "purchase", "upgrade", "phone", "car", "house"]
    }
    for tag, kws in keywords.items():
        if any(kw in s for kw in kws):
            tags.append(tag)
    if not tags:
        tags.append("general")
    return tags


def generate_debate(situation: str):
    s = situation.strip()
    tags = extract_tags(s)

    def emo_open():
        return (
            "I feel the weight of this. Your well-being and how this choice impacts your day-to-day truly matters. "
            "Let's honor your feelings first."
        )

    def logic_open():
        return (
            "Let's structure this. We'll list objectives, constraints, and potential outcomes, then score options rationally."
        )

    def emotional_points():
        pts = []
        pts.append("What outcome brings you a sense of peace and excitement when you imagine waking up tomorrow?")
        pts.append("Consider your energy: which option avoids burnout and supports your mental health?")
        pts.append("Your relationships and identity matter—will this choice align with your values and community?")
        return pts

    def logical_points():
        pts = []
        pts.append("Map pros and cons with time horizons: immediate, 6 months, 2 years.")
        pts.append("Estimate risk vs. reward. Minimize irreversible downside, capture asymmetric upside.")
        pts.append("Define a small reversible experiment to test before fully committing.")
        return pts

    messages = []
    turn = 1
    messages.append({"role": "user", "content": s, "turn": 0})
    messages.append({"role": "emotional", "content": emo_open(), "turn": turn}); turn += 1
    messages.append({"role": "logical", "content": logic_open(), "turn": turn}); turn += 1

    for ep, lp in zip(emotional_points(), logical_points()):
        messages.append({"role": "emotional", "content": ep, "turn": turn}); turn += 1
        messages.append({"role": "logical", "content": lp, "turn": turn}); turn += 1

    # Balanced summary decision
    summary = []
    summary.append("Synthesis: blend care with clarity.")
    summary.append(
        "From the emotional lens: prioritize well-being, values, and sustainable motivation."
    )
    summary.append(
        "From the logical lens: choose the option with favorable expected value and low irreversible risk."
    )
    # actionable next step tailored by tags
    action = "Next step: run a 7-day experiment to gather signal and reduce uncertainty."
    if "finance" in tags:
        action = "Next step: set a 30-60-90 day budget and a small-cap downside cap; run a reversible trial."
    if "career" in tags:
        action = "Next step: set 3 success metrics (learning, compensation, impact) and do a 2-week shadow/test project."
    if "relationships" in tags:
        action = "Next step: schedule an open conversation, agree on needs and boundaries, and reassess in 2 weeks."
    if "health" in tags:
        action = "Next step: adopt a minimal viable routine (sleep, meals, 20-min walk) and review mood/energy after 10 days."

    final_decision = "Balanced Decision: choose the path that preserves mental health and aligns with values while maximizing reversible upside. " + action
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
