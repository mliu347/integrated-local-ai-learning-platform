#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import html
import io
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import subprocess
import textwrap
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.parse import unquote, urlparse


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
RUNTIME_DIR = APP_DIR / "runtime"
MATERIALS_DIR = RUNTIME_DIR / "materials"
SESSIONS_DIR = RUNTIME_DIR / "sessions"
EXPORTS_DIR = RUNTIME_DIR / "exports"
AUDITS_DIR = RUNTIME_DIR / "audits"
STUDENT_UPLOADS_DIR = RUNTIME_DIR / "student_uploads"
TTS_DIR = RUNTIME_DIR / "tts"
CONFIG_DIR = APP_DIR / "config"
TOOLS_DIR = APP_DIR / "tools"
MODELS_DIR = APP_DIR / "models"
OVERLAY_RENDERER_SOURCE = TOOLS_DIR / "subtitle_overlay_renderer.m"
OVERLAY_RENDERER_BIN = TOOLS_DIR / "subtitle_overlay_renderer"
PIPER_PYTHON = APP_DIR / ".venv-tts" / "bin" / "python"
PIPER_MODEL = MODELS_DIR / "piper" / "en_US-lessac-medium.onnx"
PIPER_CONFIG = MODELS_DIR / "piper" / "en_US-lessac-medium.onnx.json"
TRANSLATION_GLOSSARY_FILE = CONFIG_DIR / "translation_glossary.json"

MATERIALS_FILE = RUNTIME_DIR / "materials.json"
SESSIONS_FILE = RUNTIME_DIR / "sessions.json"
STUDENT_ACCOUNTS_FILE = RUNTIME_DIR / "student_accounts.json"
RESEARCH_GOVERNANCE_FILE = RUNTIME_DIR / "research_governance.json"
ACTIONS_FILE = RUNTIME_DIR / "actions.json"
SECRET_FILE = RUNTIME_DIR / "server_secret.key"
ANON_SALT_FILE = RUNTIME_DIR / "anonymisation_salt.key"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8790"))
MAX_VIDEO_SECONDS = 300
MAX_TURNS = 50
MAX_STUDENT_ACCOUNTS = 500
MAX_STUDENT_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_BURNED_SUBTITLE_OVERLAYS = 24
TOKEN_TTL_SECONDS = 8 * 60 * 60
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm"}
WHISPER_LANGUAGE_OPTIONS = {"auto", "zh", "en", "ja", "ko", "es", "fr", "de"}
SOURCE_LANGUAGE_LABELS = {
    "auto": "Auto",
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}
OLLAMA_TRANSLATION_MODEL_PREFERENCES = (
    "qwen2.5:7b",
    "qwen2.5-coder:7b",
    "qwen3:8b",
    "llama3.1:8b",
    "llama3:8b",
)
OLLAMA_DIALOGUE_MODEL_PREFERENCES = (
    "qwen2.5:7b",
    "llama3.1:8b",
    "qwen3:8b",
    "llama3:8b",
    "qwen2.5-coder:7b",
)
DEFAULT_MASK_TOP_RIGHT = (0.76, 0.00, 0.24, 0.15)
DEFAULT_MASK_BOTTOM = (0.00, 0.74, 1.00, 0.26)
SOURCE_VISUAL_FILTER = (
    "drawbox=x=iw*0.76:y=0:w=iw*0.24:h=ih*0.15:color=black:t=fill,"
    "drawbox=x=0:y=ih*0.74:w=iw:h=ih*0.26:color=black:t=fill,"
    "scale=1280:720:force_original_aspect_ratio=decrease,"
    "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x17202A"
)

for folder in (STATIC_DIR, RUNTIME_DIR, MATERIALS_DIR, SESSIONS_DIR, EXPORTS_DIR, AUDITS_DIR, STUDENT_UPLOADS_DIR, TTS_DIR, CONFIG_DIR, TOOLS_DIR, MODELS_DIR):
    folder.mkdir(parents=True, exist_ok=True)


TECH_SEDA_MOVES = {
    "IBI": "Invitation to build on ideas",
    "IR": "Invitation for reasoning",
    "R": "Reasoning",
    "EOR": "Elicitation of reasoning",
    "BI": "Building on ideas",
    "CH": "Challenge",
    "RD": "Reflection on dialogue",
    "C": "Coordination and synthesis",
    "RB": "Reference back",
    "EL": "Elaboration",
    "CQ": "Clarification question",
    "MS": "Motivational scaffolding",
    "VB": "Vocabulary bridge",
}

SCAFFOLDS = {
    "reasoning_prompt": "Ask for a reason or evidence.",
    "elaboration_invitation": "Ask the student to say more.",
    "perspective_shift": "Invite another possible view.",
    "metacognitive_prompt": "Ask the student to reflect on their thinking.",
    "example_invitation": "Ask for a concrete example.",
    "vocabulary_bridge": "Provide accessible English words or sentence starters.",
    "synthesis_prompt": "Connect earlier and current ideas.",
    "autonomy_support": "Offer choice and avoid pressure.",
}

DEFAULT_TRANSLATION_GLOSSARY = {
    "source_terms": [
        {"source": ["小气", "抠门", "吝啬"], "target": "stingy", "sentence": "The person is being stingy."},
        {"source": ["浪费钱", "乱花钱"], "target": "waste money", "sentence": "The person is wasting money."},
        {"source": ["搭讪"], "target": "start a conversation", "sentence": "The person is trying to start a conversation."},
        {"source": ["说什么傻话", "傻话"], "target": "nonsense", "sentence": "The person says this sounds like nonsense."},
        {"source": ["本地文化", "地方文化"], "target": "local culture", "sentence": "The video is about local culture."},
        {"source": ["朋友", "友谊"], "target": "friendship", "sentence": "The video talks about friendship."},
        {"source": ["网络安全", "上网安全"], "target": "online safety", "sentence": "The video talks about online safety."},
    ],
    "english_post_edits": [
        {"pattern": r"\bXiao\s*Qi\b|\bXiaoqi\b|\bsmall\s+gas\b", "replace": "stingy", "when_source_contains": ["小气", "抠门", "吝啬"]},
        {"pattern": r"\bbig fan\b", "replace": "start a conversation", "when_source_contains": ["搭讪"]},
        {"pattern": r"\bsucceed\s+in\s+flirting\b", "replace": "manage to start a conversation", "when_source_contains": ["搭讪"]},
        {"pattern": r"\bflirt(?:ing)?\b|\bhit\s+on\b", "replace": "start a conversation", "when_source_contains": ["搭讪"]},
        {"pattern": r"\bwaste\s+money\s+money\b", "replace": "waste money"},
        {"pattern": r"\bthe beautiful girl's reaction to waste money\b", "replace": "the girl's reaction when someone wastes money"},
    ],
}

DIALOGUE_VARIANTS = {
    "ack": [
        "That gives us a path.",
        "There is something to explore there.",
        "I can work with that idea.",
        "Let's make that idea clearer.",
        "That points to a useful question.",
    ],
    "IBI": [
        "What is one detail from the video that connects with your idea?",
        "Can you add one example from the video?",
        "Who is affected by this idea?",
    ],
    "EOR": [
        "What is one reason behind that view?",
        "Why do you think this matters in real life?",
        "What evidence from the video or your experience supports it?",
    ],
    "CH": [
        "What might someone who disagrees say?",
        "Can you imagine one fair opposite view?",
        "What is one situation where this idea might not work?",
    ],
    "RD": [
        "What helped you form that idea: the video, your experience, or a word you heard?",
        "How did your thinking change after watching the video?",
        "Which part felt easy or difficult to explain in English?",
    ],
    "BI": [
        "Can you add one concrete example?",
        "Can you connect this idea with a person or event in the video?",
        "What small detail would make your point clearer?",
    ],
    "C": [
        "Can you give one sentence that connects your main ideas so far?",
        "What is the most important idea from our discussion now?",
        "How would you explain your final point to a classmate?",
    ],
    "MS": [
        "Choose one scene from the video, and tell me what happened there.",
        "Pick one person in the video, and say what they did.",
        "Use one short sentence about the clearest moment you remember.",
    ],
    "VB": [
        "Let's make the language smaller first. Which word do you want to use in your next sentence?",
        "A useful pattern is: I think this because... What word should we put after because?",
        "We can build one clear sentence. What is the key word you want to say?",
    ],
}

DEFAULT_TOPICS = {
    "online-safety": {
        "title": "Online Safety",
        "zh": "网络安全",
        "script": (
            "Online safety is important for teenagers. Students often watch videos, chat with friends, and search for information online. "
            "A safe user protects personal information, checks whether information is reliable, and speaks to others with respect. "
            "When something online feels uncomfortable, students should stop, save evidence if needed, and ask a trusted adult for help. "
            "In English discussion, students can explain one safe habit, give one reason, and ask one thoughtful question."
        ),
        "vocabulary": "safe, personal information, reliable, evidence, trusted adult",
    },
    "local-culture": {
        "title": "Local Culture",
        "zh": "本地文化",
        "script": (
            "Local culture gives students a real reason to speak English. A village, town, or city may have special food, stories, buildings, or ways of life. "
            "When students introduce local culture, they share identity and memory. Classmates can ask questions, compare experiences, and build respect for different places."
        ),
        "vocabulary": "local culture, hometown, story, tradition, respect",
    },
    "friendship": {
        "title": "Friendship and Communication",
        "zh": "友谊与沟通",
        "script": (
            "Friendship grows through communication, trust, and small acts of care. Good friends do not always agree, but they try to listen and speak honestly. "
            "When a problem happens, students can use calm words, explain feelings, and look for a fair solution."
        ),
        "vocabulary": "friendship, listen, trust, feeling, solution",
    },
}

SAFETY_INPUT_RULES = {
    "self_harm_or_distress": ["suicide", "self-harm", "hurt myself", "kill myself", "自杀", "自残", "轻生", "不想活"],
    "bullying_or_threat": ["bully", "bullying", "threaten", "hit me", "欺负", "霸凌", "威胁", "打我"],
    "direct_identifier": ["my phone number", "my address", "my id card", "我家地址", "身份证", "手机号", "电话号码"],
}

SAFETY_OUTPUT_RULES = {
    "personal_data_request": ["tell me your full name", "give me your phone number", "send me your photo", "share your password"],
    "shaming": ["you are stupid", "you are lazy", "that is dumb"],
    "age_inappropriate": ["porn", "sexual", "drug dealing", "weapon"],
}

REASONING_MARKERS = ["because", "i think", "therefore", "maybe", "for example", "in my opinion", "因为", "所以", "我认为", "例如"]
CLARIFICATION_MARKERS = ["what does", "what mean", "explain", "i don't understand", "什么意思", "解释", "不懂", "不会说"]


MATERIALS: dict[str, dict] = {}
SESSIONS: dict[str, dict] = {}
STUDENT_ACCOUNTS: dict[str, dict] = {}
RESEARCH_GOVERNANCE: dict = {}


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def default_research_governance() -> dict:
    return {
        "classes": {},
        "students": {},
        "current_lesson": {
            "unit": "Unit 1",
            "lesson_cycle": "in_class",
            "phase": "in_class",
            "curriculum_focus": "dialogic English learning",
            "updated_at": now_iso(),
        },
        "assessment_records": [],
        "fidelity_logs": [],
        "comparison_logs": [],
        "human_coding": [],
        "imi_surveys": [],
        "teacher_reflections": [],
        "safeguarding_cases": [],
        "dataset_approvals": [],
    }


def normalise_research_governance(data: dict | None) -> dict:
    base = default_research_governance()
    if isinstance(data, dict):
        for key, value in data.items():
            base[key] = value
    for key, value in default_research_governance().items():
        if key not in base or not isinstance(base[key], type(value)):
            base[key] = value
    return base


def load_state() -> None:
    global MATERIALS, SESSIONS, STUDENT_ACCOUNTS, RESEARCH_GOVERNANCE
    MATERIALS = load_json(MATERIALS_FILE, {})
    SESSIONS = load_json(SESSIONS_FILE, {})
    STUDENT_ACCOUNTS = load_json(STUDENT_ACCOUNTS_FILE, {})
    RESEARCH_GOVERNANCE = normalise_research_governance(load_json(RESEARCH_GOVERNANCE_FILE, {}))
    rebuild_student_accounts_from_sessions(save=False)


def save_materials() -> None:
    save_json(MATERIALS_FILE, MATERIALS)


def save_sessions() -> None:
    save_json(SESSIONS_FILE, SESSIONS)


def save_student_accounts() -> None:
    save_json(STUDENT_ACCOUNTS_FILE, STUDENT_ACCOUNTS)


def save_research_governance() -> None:
    save_json(RESEARCH_GOVERNANCE_FILE, RESEARCH_GOVERNANCE)


def ensure_secret(path: Path, length: int = 32) -> bytes:
    if path.exists():
        return path.read_bytes()
    secret = secrets.token_bytes(length)
    path.write_bytes(secret)
    return secret


SERVER_SECRET = ensure_secret(SECRET_FILE)
ANON_SALT = ensure_secret(ANON_SALT_FILE)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))


def make_token(role: str) -> str:
    payload = {"role": role, "exp": int(time.time()) + TOKEN_TTL_SECONDS, "iat": int(time.time())}
    body = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = b64url(hmac.new(SERVER_SECRET, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> str | None:
    if "." not in token:
        return None
    body, sig = token.split(".", 1)
    expected = b64url(hmac.new(SERVER_SECRET, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(b64url_decode(body).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    role = payload.get("role")
    return role if role in {"teacher", "researcher"} else None


def participant_hash(code: str) -> str:
    return hashlib.sha256(ANON_SALT + code.encode("utf-8")).hexdigest()[:18]


def sanitize_code(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "", value or "")
    return value[:32] or "ANON-001"


def student_account_key(participant_code: str) -> str:
    return sanitize_code(participant_code)


def register_student_account(payload: dict, session: dict | None = None, save: bool = True) -> dict:
    code = student_account_key(payload.get("participant_code") or payload.get("student_id") or payload.get("code") or "")
    is_new = code not in STUDENT_ACCOUNTS
    if is_new and len(STUDENT_ACCOUNTS) >= MAX_STUDENT_ACCOUNTS:
        raise ValueError(f"Student account limit reached ({MAX_STUDENT_ACCOUNTS}).")
    level = payload.get("level") if payload.get("level") in {"A1", "A2", "B1"} else (session or {}).get("level", "A2")
    now = now_iso()
    account = STUDENT_ACCOUNTS.get(code) or {
        "participant_code": code,
        "participant_hash": participant_hash(code),
        "created_at": now,
        "session_ids": [],
        "registration_source": payload.get("source", "student"),
    }
    account.update(
        {
            "level": level,
            "updated_at": now,
            "last_seen_at": now,
            "account_status": payload.get("account_status", account.get("account_status", "registered")),
        }
    )
    if session:
        session_ids = account.get("session_ids", [])
        if session["id"] not in session_ids:
            session_ids.append(session["id"])
        account.update(
            {
                "active_session_id": session["id"],
                "session_ids": session_ids[-80:],
                "last_material_title": session.get("material_title"),
                "last_material_id": session.get("material_id"),
                "current_session_status": session.get("status"),
                "current_chatbot_listening": bool(session.get("chatbot_listening", False)),
                "turn_count": len(session.get("turns", [])),
                "flag_count": len(session.get("flags", [])),
                "last_turn_at": session.get("turns", [{}])[-1].get("timestamp") if session.get("turns") else None,
            }
        )
    STUDENT_ACCOUNTS[code] = account
    if save:
        save_student_accounts()
    return account


def sync_student_account_from_session(session: dict, save: bool = True) -> dict:
    return register_student_account(
        {
            "participant_code": session.get("participant_code", ""),
            "level": session.get("level", "A2"),
            "account_status": "connected" if session.get("status") == "active" else session.get("status", "registered"),
            "source": "session_sync",
        },
        session=session,
        save=save,
    )


def rebuild_student_accounts_from_sessions(save: bool = True) -> None:
    for session in sorted(SESSIONS.values(), key=lambda item: item.get("created_at", "")):
        try:
            sync_student_account_from_session(session, save=False)
        except ValueError:
            break
    if save:
        save_student_accounts()


def current_lesson_context() -> dict:
    return dict(RESEARCH_GOVERNANCE.get("current_lesson") or default_research_governance()["current_lesson"])


def upsert_class_group(payload: dict, role: str) -> dict:
    class_id = sanitize_code(payload.get("class_id") or payload.get("class") or "")
    if not class_id:
        raise ValueError("Class ID is required.")
    condition = payload.get("condition") if payload.get("condition") in {"treatment", "comparison"} else "treatment"
    record = {
        "class_id": class_id,
        "grade": re.sub(r"\s+", " ", str(payload.get("grade") or "Grade 8").strip())[:60],
        "teacher_id": sanitize_code(payload.get("teacher_id") or "TEACHER-001"),
        "condition": condition,
        "pair_id": sanitize_code(payload.get("pair_id") or f"PAIR-{class_id}"),
        "school_level": re.sub(r"\s+", " ", str(payload.get("school_level") or "secondary").strip())[:80],
        "updated_at": now_iso(),
        "updated_by": role,
    }
    existing = RESEARCH_GOVERNANCE.setdefault("classes", {}).get(class_id, {})
    record["created_at"] = existing.get("created_at", now_iso())
    RESEARCH_GOVERNANCE["classes"][class_id] = {**existing, **record}
    save_research_governance()
    log_action(role, "research_class_upserted", {"class_id": class_id, "condition": condition})
    return RESEARCH_GOVERNANCE["classes"][class_id]


def upsert_research_student(payload: dict, role: str) -> dict:
    code = sanitize_code(payload.get("participant_code") or payload.get("student_id") or "")
    if not code:
        raise ValueError("Student anonymous ID is required.")
    account = register_student_account({"participant_code": code, "level": payload.get("level", "A2"), "source": "research_roster"}, save=False)
    bool_value = lambda key, default=False: bool(payload.get(key, default))
    include = not bool_value("withdrawn", False) and bool_value("guardian_consent", True) and bool_value("student_assent", True)
    if "include_in_dataset" in payload:
        include = bool_value("include_in_dataset", include)
    record = {
        "participant_code": code,
        "participant_hash": account["participant_hash"],
        "class_id": sanitize_code(payload.get("class_id") or payload.get("class") or ""),
        "grade": re.sub(r"\s+", " ", str(payload.get("grade") or account.get("grade") or "Grade 8").strip())[:60],
        "teacher_id": sanitize_code(payload.get("teacher_id") or ""),
        "condition": payload.get("condition") if payload.get("condition") in {"treatment", "comparison"} else payload.get("condition", "treatment"),
        "level": payload.get("level") if payload.get("level") in {"A1", "A2", "B1"} else account.get("level", "A2"),
        "guardian_consent": bool_value("guardian_consent", True),
        "student_assent": bool_value("student_assent", True),
        "withdrawn": bool_value("withdrawn", False),
        "include_in_dataset": include,
        "updated_at": now_iso(),
        "updated_by": role,
    }
    existing = RESEARCH_GOVERNANCE.setdefault("students", {}).get(code, {})
    record["created_at"] = existing.get("created_at", now_iso())
    RESEARCH_GOVERNANCE["students"][code] = {**existing, **record}
    account.update(
        {
            "class_id": record["class_id"],
            "grade": record["grade"],
            "teacher_id": record["teacher_id"],
            "condition": record["condition"],
            "guardian_consent": record["guardian_consent"],
            "student_assent": record["student_assent"],
            "withdrawn": record["withdrawn"],
            "include_in_dataset": record["include_in_dataset"],
        }
    )
    STUDENT_ACCOUNTS[code] = account
    save_student_accounts()
    save_research_governance()
    log_action(role, "research_student_upserted", {"participant_hash": account["participant_hash"], "class_id": record["class_id"]})
    return RESEARCH_GOVERNANCE["students"][code]


def set_lesson_context(payload: dict, role: str) -> dict:
    lesson = {
        "unit": re.sub(r"\s+", " ", str(payload.get("unit") or "Unit 1").strip())[:80],
        "lesson_cycle": payload.get("lesson_cycle") if payload.get("lesson_cycle") in {"pre_class", "in_class", "post_class"} else "in_class",
        "phase": payload.get("phase") if payload.get("phase") in {"pre_class", "in_class", "post_class"} else payload.get("lesson_cycle", "in_class"),
        "curriculum_focus": re.sub(r"\s+", " ", str(payload.get("curriculum_focus") or "").strip())[:240],
        "class_id": sanitize_code(payload.get("class_id") or ""),
        "updated_at": now_iso(),
        "updated_by": role,
    }
    if not lesson["curriculum_focus"]:
        lesson["curriculum_focus"] = "dialogic English learning"
    RESEARCH_GOVERNANCE["current_lesson"] = lesson
    save_research_governance()
    log_action(role, "research_lesson_context_updated", lesson)
    return lesson


def append_research_record(collection: str, payload: dict, role: str) -> dict:
    record = {key: value for key, value in payload.items() if key not in {"token"}}
    record["id"] = uuid.uuid4().hex[:12]
    record["created_at"] = now_iso()
    record["created_by"] = role
    if "participant_code" in record:
        record["participant_code"] = sanitize_code(record.get("participant_code", ""))
        record["participant_hash"] = participant_hash(record["participant_code"]) if record["participant_code"] else ""
    RESEARCH_GOVERNANCE.setdefault(collection, []).append(record)
    RESEARCH_GOVERNANCE[collection] = RESEARCH_GOVERNANCE[collection][-5000:]
    save_research_governance()
    log_action(role, f"research_{collection}_record_added", {"id": record["id"]})
    return record


def import_assessment_records(payload: dict, role: str) -> dict:
    csv_text = payload.get("csv") or payload.get("csv_text") or ""
    if not csv_text.strip():
        raise ValueError("CSV text is required.")
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    imported = []
    required = {"participant_code", "measure", "timepoint", "score"}
    if not reader.fieldnames or not required.issubset({field.strip() for field in reader.fieldnames}):
        raise ValueError("CSV must include participant_code, measure, timepoint, score.")
    for row in reader:
        code = sanitize_code(row.get("participant_code") or "")
        if not code:
            continue
        try:
            score = float(str(row.get("score", "")).strip())
        except ValueError:
            continue
        research_student = RESEARCH_GOVERNANCE.get("students", {}).get(code, {})
        record = {
            "id": uuid.uuid4().hex[:12],
            "participant_code": code,
            "participant_hash": participant_hash(code),
            "class_id": sanitize_code(row.get("class_id") or research_student.get("class_id", "")),
            "condition": row.get("condition") or research_student.get("condition", ""),
            "measure": re.sub(r"\s+", " ", str(row.get("measure", "")).strip())[:120],
            "timepoint": re.sub(r"\s+", " ", str(row.get("timepoint", "")).strip())[:80],
            "score": score,
            "max_score": float(row.get("max_score") or 100),
            "date": re.sub(r"\s+", " ", str(row.get("date", "")).strip())[:40],
            "source": re.sub(r"\s+", " ", str(row.get("source", "imported_csv")).strip())[:120],
            "created_at": now_iso(),
            "created_by": role,
        }
        imported.append(record)
    RESEARCH_GOVERNANCE.setdefault("assessment_records", []).extend(imported)
    RESEARCH_GOVERNANCE["assessment_records"] = RESEARCH_GOVERNANCE["assessment_records"][-20000:]
    save_research_governance()
    log_action(role, "research_assessments_imported", {"count": len(imported)})
    return {"imported_count": len(imported), "records": imported[:12]}


def upsert_safeguarding_case(payload: dict, role: str) -> dict:
    case_id = payload.get("case_id") or uuid.uuid4().hex[:12]
    cases = RESEARCH_GOVERNANCE.setdefault("safeguarding_cases", [])
    existing = next((item for item in cases if item.get("id") == case_id), None)
    status = payload.get("status") if payload.get("status") in {"unresolved", "reviewed", "referred", "excluded", "closed"} else "unresolved"
    record = existing or {"id": case_id, "created_at": now_iso(), "history": []}
    update = {
        "participant_code": sanitize_code(payload.get("participant_code") or record.get("participant_code", "")),
        "session_id": payload.get("session_id") or record.get("session_id", ""),
        "status": status,
        "severity": payload.get("severity") if payload.get("severity") in {"low", "medium", "high"} else payload.get("severity", "medium"),
        "note": re.sub(r"\s+", " ", str(payload.get("note") or "").strip())[:1200],
        "updated_at": now_iso(),
        "updated_by": role,
    }
    if update["participant_code"]:
        update["participant_hash"] = participant_hash(update["participant_code"])
    record.update(update)
    record.setdefault("history", []).append({"time": now_iso(), "role": role, "status": status, "note": update["note"]})
    if not existing:
        cases.append(record)
    save_research_governance()
    log_action(role, "research_safeguarding_case_updated", {"case_id": case_id, "status": status})
    return record


def save_dataset_approval(payload: dict, role: str) -> dict:
    approval = {
        "id": uuid.uuid4().hex[:12],
        "created_at": now_iso(),
        "created_by": role,
        "scope": payload.get("scope") if payload.get("scope") in {"selected", "all", "class", "condition"} else "all",
        "class_id": sanitize_code(payload.get("class_id") or ""),
        "condition": payload.get("condition") if payload.get("condition") in {"treatment", "comparison"} else "",
        "exclude_flagged": bool(payload.get("exclude_flagged", True)),
        "include_fields": payload.get("include_fields") if isinstance(payload.get("include_fields"), list) else ["turns", "assessments", "coding", "surveys"],
        "approval_note": re.sub(r"\s+", " ", str(payload.get("approval_note") or "").strip())[:1200],
    }
    RESEARCH_GOVERNANCE.setdefault("dataset_approvals", []).append(approval)
    save_research_governance()
    log_action(role, "research_dataset_approval_saved", {"approval_id": approval["id"]})
    return approval


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return value.strip("-")[:80] or "item"


def truthy_field(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "checked"}


def parse_custom_mask(value: str) -> tuple[float, float, float, float] | None:
    parts = [item.strip() for item in re.split(r"[,，\s]+", value or "") if item.strip()]
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = [float(item) for item in parts]
    except ValueError:
        return None
    values = (x, y, w, h)
    if any(item < 0 or item > 1 for item in values):
        return None
    if w <= 0 or h <= 0 or x + w > 1.02 or y + h > 1.02:
        return None
    return values


def build_source_visual_filter(mask_options: dict | None = None) -> str:
    options = mask_options or {}
    masks: list[tuple[float, float, float, float]] = []
    if options.get("mask_top", True):
        masks.append(DEFAULT_MASK_TOP_RIGHT)
    if options.get("mask_bottom", True):
        masks.append(DEFAULT_MASK_BOTTOM)
    custom = options.get("custom_mask")
    if custom:
        masks.append(custom)
    filters = [
        f"drawbox=x=iw*{x:.4f}:y=ih*{y:.4f}:w=iw*{w:.4f}:h=ih*{h:.4f}:color=black:t=fill"
        for x, y, w, h in masks
    ]
    filters.extend(
        [
            "scale=1280:720:force_original_aspect_ratio=decrease",
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x17202A",
        ]
    )
    return ",".join(filters)


def piper_espeak_data_dir() -> Path | None:
    direct = APP_DIR / ".venv-tts" / "lib" / "python3.11" / "site-packages" / "piper" / "espeak-ng-data"
    if direct.exists():
        return direct
    lib_dir = APP_DIR / ".venv-tts" / "lib"
    for candidate in lib_dir.glob("python*/site-packages/piper/espeak-ng-data"):
        if candidate.exists():
            return candidate
    return None


def ensure_piper_espeak_compatibility() -> bool:
    data_dir = piper_espeak_data_dir()
    if not data_dir:
        return False
    package_dir = data_dir.parent
    try:
        for child in data_dir.iterdir():
            target = package_dir / child.name
            if target.exists():
                continue
            try:
                os.symlink(child, target, target_is_directory=child.is_dir())
            except OSError:
                if child.is_dir():
                    shutil.copytree(child, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, target)
        return (package_dir / "phontab").exists()
    except OSError:
        return False


def piper_available() -> bool:
    return bool(PIPER_PYTHON.exists() and PIPER_MODEL.exists() and PIPER_CONFIG.exists() and ensure_piper_espeak_compatibility())


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def log_action(role: str, action: str, details: dict | None = None) -> None:
    actions = load_json(ACTIONS_FILE, [])
    actions.append({"time": now_iso(), "role": role, "action": action, "details": details or {}})
    save_json(ACTIONS_FILE, actions[-700:])


def rel_media(path: Path) -> str:
    return "/media/" + path.resolve().relative_to(RUNTIME_DIR.resolve()).as_posix()


def safe_runtime_path(relative_path: str) -> Path | None:
    raw = unquote(relative_path).lstrip("/")
    path = (RUNTIME_DIR / raw).resolve()
    try:
        path.relative_to(RUNTIME_DIR.resolve())
    except ValueError:
        return None
    return path


def clean_upload_metadata(upload) -> dict | None:
    if not isinstance(upload, dict):
        return None
    upload_id = sanitize_code(upload.get("id", ""))
    url = str(upload.get("url", ""))[:240]
    if not upload_id or not url.startswith("/media/student_uploads/"):
        return None
    return {
        "id": upload_id,
        "url": url,
        "original_filename": Path(str(upload.get("original_filename", "student-video"))).name[:120],
        "stored_filename": Path(str(upload.get("stored_filename", "video"))).name[:120],
        "size_bytes": int(upload.get("size_bytes") or 0),
        "uploaded_at": str(upload.get("uploaded_at", now_iso()))[:32],
        "system1_adaptation": upload.get("system1_adaptation") if isinstance(upload.get("system1_adaptation"), dict) else None,
    }


def receive_student_video_upload(handler: BaseHTTPRequestHandler) -> dict:
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Expected multipart video upload.")
    if content_length <= 0:
        raise ValueError("Uploaded video is empty.")
    if content_length > MAX_STUDENT_UPLOAD_BYTES:
        raise ValueError("Uploaded video is larger than the local 5-minute converter limit. Please compress it or use a shorter file.")

    boundary = multipart_boundary(content_type)
    if not boundary:
        raise ValueError("Upload boundary is missing.")
    body = handler.rfile.read(content_length)
    fields, files = extract_multipart_form(body, boundary)
    original_filename, video_bytes = files.get("video", ("", b""))
    if not original_filename or not video_bytes:
        raise ValueError("No video file was uploaded.")

    original_filename = Path(original_filename).name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Please upload an MP4, M4V, MOV, or WebM video.")

    upload_id = uuid.uuid4().hex[:12]
    folder = STUDENT_UPLOADS_DIR / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{slug(Path(original_filename).stem)[:60] or 'student-video'}{extension}"
    target = folder / stored_filename
    target.write_bytes(video_bytes)
    source_duration = probe_duration(target)
    if source_duration is not None and source_duration > MAX_VIDEO_SECONDS:
        raise ValueError(f"Uploaded video is {source_duration:.1f}s. This local converter is configured for videos up to 5 minutes.")

    playable_target = make_uploaded_video_playable(target, folder)
    adaptation = build_student_video_adaptation(
        folder,
        original_filename,
        fields.get("source_topic", ""),
        fields.get("source_summary", ""),
        fields.get("level", "A2"),
    )
    upload = {
        "id": upload_id,
        "url": rel_media(playable_target),
        "original_filename": original_filename[:120],
        "stored_filename": playable_target.name,
        "source_filename": stored_filename,
        "size_bytes": target.stat().st_size,
        "uploaded_at": now_iso(),
        "browser_playable": playable_target != target,
        "system1_adaptation": adaptation,
    }
    save_json(folder / "metadata.json", upload)
    return upload


def multipart_boundary(content_type: str) -> str:
    for item in content_type.split(";"):
        item = item.strip()
        if item.startswith("boundary="):
            return item.removeprefix("boundary=").strip('"')
    return ""


def extract_multipart_form(body: bytes, boundary: str) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    delimiter = f"--{boundary}".encode("utf-8")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_blob.decode("iso-8859-1", errors="replace")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]*)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        if content.endswith(b"--"):
            content = content[:-2]
        if filename_match:
            files[name] = (filename_match.group(1), content)
        else:
            fields[name] = content.decode("utf-8", errors="replace").strip()
    return fields, files


def build_student_video_adaptation(folder: Path, filename: str, topic: str, source_summary: str, level: str) -> dict:
    clean_topic = re.sub(r"\s+", " ", (topic or "").strip())[:100] or Path(filename).stem.replace("_", " ").replace("-", " ")[:80]
    clean_summary = re.sub(r"\s+", " ", (source_summary or "").strip())[:700]
    level = level if level in {"A1", "A2", "B1"} else "A2"
    focus = clean_summary or f"This uploaded video is about {clean_topic}."
    english_brief = adapt_script(
        (
            f"This local video is used as the student's learning source. The topic is {clean_topic}. "
            f"{focus} Students can describe what they see, explain one reason, ask one question, and connect the video with their own experience."
        ),
        level,
    )
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", f"{clean_topic} {clean_summary}")
        if word.lower() not in {"this", "that", "with", "from", "video", "student", "students", "about", "their", "because"}
    ]
    vocabulary = []
    for word in words:
        if word not in vocabulary:
            vocabulary.append(word)
        if len(vocabulary) >= 6:
            break
    if len(vocabulary) < 4:
        vocabulary.extend(["describe", "reason", "example", "question"])
    vocabulary = vocabulary[:6]
    prompts = [
        "I notice...",
        "This matters because...",
        "One question I have is...",
        "This connects to my experience because...",
    ]
    subtitle_path = folder / "system1_adaptation.vtt"
    subtitle_lines = [
        "WEBVTT\n",
        f"{vtt_time(0.4)} --> {vtt_time(4.4)}\nSystem 1 adaptation: {clean_topic}\n",
        f"{vtt_time(4.7)} --> {vtt_time(9.2)}\nDescribe one thing you see. Then give one reason.\n",
        f"{vtt_time(9.5)} --> {vtt_time(14.2)}\nSentence starter: {prompts[1]}\n",
    ]
    subtitle_path.write_text("\n".join(subtitle_lines), encoding="utf-8")
    return {
        "title": f"My Video: {clean_topic}",
        "source_topic": clean_topic,
        "source_summary": clean_summary,
        "level": level,
        "english_brief": english_brief,
        "key_vocabulary": ", ".join(vocabulary),
        "dialogue_prompts": prompts,
        "subtitles_vtt": rel_media(subtitle_path),
        "generated_at": now_iso(),
    }


def make_uploaded_video_playable(source: Path, folder: Path) -> Path:
    if not shutil.which("ffmpeg"):
        return source
    output = folder / "student_video_playable.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
        return output
    return source


def detect_learning_topic(text: str) -> str:
    lowered = (text or "").lower()
    probes = [
        ("friendship", ["friend", "listen", "communication", "朋友", "友谊", "沟通", "倾听"]),
        ("local-culture", ["culture", "hometown", "tradition", "local", "家乡", "文化", "传统", "本地"]),
        ("online-safety", ["online", "internet", "phone", "网络", "手机", "短视频", "个人信息", "信息安全"]),
    ]
    for topic_id, words in probes:
        if any(word in lowered or word in text for word in words):
            return topic_id
    return "local-culture"


def vocabulary_from_text(text: str, fallback: str) -> str:
    words = []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text):
        clean = word.lower().strip("'")
        if clean in {"this", "that", "with", "from", "video", "student", "students", "about", "their", "because", "learning", "english"}:
            continue
        if clean not in words:
            words.append(clean)
        if len(words) >= 5:
            break
    return ", ".join(words) if words else fallback


def run_local_text_command(env_name: str, input_text: str, output_path: Path, input_path: Path | None = None) -> str | None:
    command_template = os.getenv(env_name)
    if not command_template:
        return None
    input_text_path = output_path.with_suffix(".input.txt")
    input_text_path.write_text(input_text, encoding="utf-8")
    command = command_template.format(input_text=str(input_text_path), input_file=str(input_path or ""), output=str(output_path))
    result = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=300, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{env_name} failed: {result.stderr.strip() or result.stdout.strip()}")
    if output_path.exists():
        return output_path.read_text(encoding="utf-8").strip()
    return result.stdout.strip()


def ollama_command() -> str | None:
    configured = os.getenv("OLLAMA_BIN")
    candidates = [
        configured,
        shutil.which("ollama"),
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def ollama_available_model(purpose: str = "translation") -> str | None:
    if purpose == "dialogue":
        configured = os.getenv("SYSTEM2_OLLAMA_MODEL") or os.getenv("OLLAMA_DIALOGUE_MODEL")
        preferences = OLLAMA_DIALOGUE_MODEL_PREFERENCES
    else:
        configured = os.getenv("SYSTEM1_OLLAMA_MODEL") or os.getenv("OLLAMA_TRANSLATION_MODEL")
        preferences = OLLAMA_TRANSLATION_MODEL_PREFERENCES
    if configured:
        return configured
    command = ollama_command()
    if not command:
        return None
    try:
        result = subprocess.run([command, "list"], capture_output=True, text=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b")
    names = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    for preferred in preferences:
        if preferred in names:
            return preferred
    return names[0] if names else os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b")


def extract_json_array(text: str):
    cleaned = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text or "")
    cleaned = cleaned.replace("\r", "")
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned.strip(), flags=re.I | re.M).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed["items"]
        return [parsed] if isinstance(parsed, dict) else parsed
    except json.JSONDecodeError:
        pass
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                return parsed["items"]
            return [parsed] if isinstance(parsed, dict) else parsed
        except json.JSONDecodeError:
            return None
    return None


def run_ollama_prompt(
    model: str,
    prompt: str,
    timeout: int,
    temperature: float = 0.1,
    top_p: float = 0.85,
    num_predict: int | None = None,
) -> tuple[str | None, str | None]:
    options = {"temperature": temperature, "top_p": top_p}
    if num_predict:
        options["num_predict"] = num_predict
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": options,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        request = urlrequest.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("response", "")).strip(), None
    except Exception as http_exc:
        try:
            command = ollama_command()
            if not command:
                return None, f"http: {http_exc}; command: ollama executable not found"
            result = subprocess.run(
                [command, "run", model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env={**os.environ, "TERM": "dumb", "OLLAMA_NO_COLOR": "1"},
            )
        except (OSError, subprocess.TimeoutExpired) as cmd_exc:
            return None, f"http: {http_exc}; command: {cmd_exc}"
        if result.returncode != 0:
            return None, f"http: {http_exc}; command: {result.stderr or result.stdout}"
        return result.stdout, None


def llm_post_edit_segments(segments: list[dict], folder: Path, level: str = "A2") -> tuple[list[dict], str | None, int]:
    model = ollama_available_model()
    if not model or not segments:
        return segments, None, 0
    batch_size = int(os.getenv("SYSTEM1_LLM_TRANSLATION_BATCH", "24") or "24")
    batch_size = max(4, min(32, batch_size))
    edited_count = 0
    report = []
    updated_segments = [dict(segment) for segment in segments]
    for offset in range(0, len(updated_segments), batch_size):
        batch = updated_segments[offset : offset + batch_size]
        items = [
            {
                "index": int(segment.get("index", offset + local_index)),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "source_text": segment.get("source_text", ""),
                "rough_english": segment.get("raw_english") or segment.get("english", ""),
            }
            for local_index, segment in enumerate(batch)
        ]
        prompt = (
            "You are a careful Chinese-to-English dubbing translator for junior secondary English learners.\n"
            f"Target CEFR level: {level}.\n"
            "Task: repair Whisper's rough English translation using the source text and timing. Preserve the original meaning. "
            "Use natural spoken English, short sentences, no pinyin, no explanations, no extra ideas. "
            "Keep each line short enough for the original time slot.\n"
            "Return ONLY valid JSON in this exact form: "
            '{"items":[{"index":0,"english":"Natural English sentence."}]}\n'
            f"Input JSON:\n{json.dumps(items, ensure_ascii=False)}"
        )
        output, error = run_ollama_prompt(model, prompt, max(90, 20 * len(batch)))
        if error or not output:
            (folder / f"ollama_translation_batch_{offset:03d}_error.log").write_text(error or "empty ollama response", encoding="utf-8")
            continue
        parsed = extract_json_array(output)
        if not isinstance(parsed, list):
            (folder / f"ollama_translation_batch_{offset:03d}_raw.txt").write_text(output, encoding="utf-8")
            continue
        by_index = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                by_index[int(item.get("index"))] = re.sub(r"\s+", " ", str(item.get("english", ""))).strip()
            except (TypeError, ValueError):
                continue
        for segment in batch:
            index = int(segment.get("index", 0))
            llm_english = by_index.get(index, "")
            if not llm_english or len(llm_english.split()) > 36:
                continue
            glossary_english, edits = apply_translation_glossary(segment.get("source_text", ""), llm_english, append_missing_terms=False)
            old_english = segment.get("english", "")
            if glossary_english and glossary_english.lower() != old_english.lower():
                segment["pre_llm_english"] = old_english
                segment["english"] = glossary_english
                segment["llm_translation_model"] = model
                segment["llm_translation_post_edits"] = edits
                edited_count += 1
                report.append(
                    {
                        "index": index,
                        "source_text": segment.get("source_text", ""),
                        "before": old_english,
                        "after": glossary_english,
                        "glossary_edits": edits,
                    }
                )
    if report:
        save_json(folder / "llm_translation_post_edit_report.json", {"model": model, "edited_count": edited_count, "items": report})
    return updated_segments, model, edited_count


def first_existing_path(candidates: list[str | Path]) -> Path | None:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def find_whisper_cpp_binary() -> Path | None:
    configured = os.getenv("WHISPER_CPP_BIN")
    if configured and Path(configured).expanduser().exists():
        return Path(configured).expanduser()
    for command in ("whisper-cli", "whisper-cpp", "main"):
        found = shutil.which(command)
        if found:
            return Path(found)
    return first_existing_path(
        [
            "/opt/homebrew/bin/whisper-cli",
            "/opt/homebrew/bin/whisper-cpp",
            "/usr/local/bin/whisper-cli",
            "/usr/local/bin/whisper-cpp",
        ]
    )


def find_whisper_model() -> Path | None:
    configured = os.getenv("WHISPER_MODEL")
    if configured and Path(configured).expanduser().exists():
        return Path(configured).expanduser()
    candidates = [
        MODELS_DIR / "ggml-small.bin",
        MODELS_DIR / "ggml-base.bin",
        MODELS_DIR / "ggml-tiny.bin",
        "/opt/homebrew/share/whisper-cpp/ggml-small.bin",
        "/opt/homebrew/share/whisper-cpp/ggml-base.bin",
        "/usr/local/share/whisper-cpp/ggml-small.bin",
        "/usr/local/share/whisper-cpp/ggml-base.bin",
    ]
    return first_existing_path(candidates)


def extract_transcription_audio(source_video: Path, folder: Path) -> Path | None:
    if not shutil.which("ffmpeg"):
        return None
    audio_path = folder / "transcription_audio.wav"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(source_video), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio_path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path
    (folder / "transcription_audio_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
    return None


def transcribe_with_whisper_cpp(source_video: Path, folder: Path) -> tuple[str | None, str, str | None]:
    binary = find_whisper_cpp_binary()
    model = find_whisper_model()
    if not binary or not model:
        return None, "missing_whisper_cpp_or_model", None
    audio_path = extract_transcription_audio(source_video, folder)
    if not audio_path:
        return None, "audio_extraction_failed", None
    output_base = folder / "transcript_zh"
    output_txt = folder / "transcript_zh.txt"
    result = subprocess.run(
        [str(binary), "-ng", "-m", str(model), "-f", str(audio_path), "-l", "zh", "-nt", "-otxt", "-of", str(output_base)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        (folder / "whisper_cpp_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
        return None, "whisper_cpp_failed", None
    transcript = output_txt.read_text(encoding="utf-8").strip() if output_txt.exists() else result.stdout.strip()
    transcript = re.sub(r"\[[^\]]+\]", " ", transcript)
    transcript = re.sub(r"\s+", " ", transcript).strip()
    if transcript:
        output_txt.write_text(transcript, encoding="utf-8")
    translation_base = folder / "translated_source_whisper"
    translation_txt = folder / "translated_source_whisper.txt"
    translation_result = subprocess.run(
        [str(binary), "-ng", "-m", str(model), "-f", str(audio_path), "-l", "zh", "-tr", "-nt", "-otxt", "-of", str(translation_base)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    translated = ""
    if translation_result.returncode == 0:
        translated = translation_txt.read_text(encoding="utf-8").strip() if translation_txt.exists() else translation_result.stdout.strip()
        translated = re.sub(r"\[[^\]]+\]", " ", translated)
        translated = re.sub(r"\s+", " ", translated).strip()
        if translated:
            translation_txt.write_text(translated, encoding="utf-8")
    else:
        (folder / "whisper_cpp_translation_error.log").write_text(translation_result.stderr or translation_result.stdout, encoding="utf-8")
    if transcript or translated:
        return transcript or translated, "local_whisper_cpp", translated or None
    return None, "empty_whisper_transcript", None


def whisper_json_time(value: str) -> float:
    match = re.fullmatch(r"\s*(\d+):(\d+):(\d+)[,.](\d+)\s*", value or "")
    if not match:
        return 0.0
    hours, minutes, seconds, millis = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis[:3].ljust(3, "0")) / 1000


def parse_whisper_segments(json_path: Path, max_duration: float | None = None, text_key: str = "english") -> list[dict]:
    data = load_json(json_path, {})
    raw_segments = data.get("transcription") if isinstance(data, dict) else []
    segments: list[dict] = []
    for index, item in enumerate(raw_segments or []):
        if not isinstance(item, dict):
            continue
        text = re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
        text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
        if not text:
            continue
        offsets = item.get("offsets") or {}
        timestamps = item.get("timestamps") or {}
        try:
            start = float(offsets.get("from", 0)) / 1000
            end = float(offsets.get("to", 0)) / 1000
        except (TypeError, ValueError):
            start = whisper_json_time(str(timestamps.get("from", "")))
            end = whisper_json_time(str(timestamps.get("to", "")))
        if end <= start:
            end = start + max(1.2, min(5.0, len(text.split()) * 0.45))
        if max_duration is not None:
            start = min(start, max_duration)
            end = min(end, max_duration)
        if end - start < 0.18:
            continue
        segments.append(
            {
                "index": len(segments),
                "source_index": index,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                text_key: clean_machine_translation(text, 64),
            }
        )
    return [segment for segment in segments if segment.get(text_key)]


def run_whisper_json(audio_path: Path, folder: Path, output_name: str, language: str, translate: bool) -> tuple[Path | None, str]:
    binary = find_whisper_cpp_binary()
    model = find_whisper_model()
    if not binary or not model:
        return None, "missing_whisper_cpp_or_model"
    output_base = folder / output_name
    output_json = Path(f"{output_base}.json")
    command = [
        str(binary),
        "-ng",
        "-m",
        str(model),
        "-f",
        str(audio_path),
        "-l",
        language if language in WHISPER_LANGUAGE_OPTIONS else "auto",
    ]
    if translate:
        command.append("-tr")
    command.extend(
        [
        "-oj",
        "-of",
        str(output_base),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=1500, check=False)
    if result.returncode != 0 or not output_json.exists():
        log_name = f"whisper_{output_name}_error.log"
        (folder / log_name).write_text(result.stderr or result.stdout, encoding="utf-8")
        return None, f"whisper_cpp_{output_name}_failed"
    return output_json, "ok"


def nearest_source_text(segment: dict, source_segments: list[dict]) -> str:
    if not source_segments:
        return ""
    start = float(segment.get("start", 0))
    end = float(segment.get("end", start))
    overlapping = []
    for candidate in source_segments:
        c_start = float(candidate.get("start", 0))
        c_end = float(candidate.get("end", c_start))
        overlap = max(0.0, min(end, c_end) - max(start, c_start))
        if overlap >= 0.12 or overlap >= max(0.05, (c_end - c_start) * 0.35):
            text = re.sub(r"\s+", " ", str(candidate.get("source_text", ""))).strip()
            if text and text not in overlapping:
                overlapping.append(text)
    if overlapping:
        return " ".join(overlapping)
    best = None
    best_score = -1.0
    for candidate in source_segments:
        c_start = float(candidate.get("start", 0))
        c_end = float(candidate.get("end", c_start))
        overlap = max(0.0, min(end, c_end) - max(start, c_start))
        distance = abs(((start + end) / 2) - ((c_start + c_end) / 2))
        score = overlap * 10 - distance
        if score > best_score:
            best = candidate
            best_score = score
    return re.sub(r"\s+", " ", str(best.get("source_text", ""))).strip() if best else ""


def translated_segments_with_whisper_cpp(source_video: Path, folder: Path, source_language: str = "auto", level: str = "A2") -> tuple[list[dict], str]:
    binary = find_whisper_cpp_binary()
    model = find_whisper_model()
    if not binary or not model:
        return [], "missing_whisper_cpp_or_model"
    audio_path = extract_transcription_audio(source_video, folder)
    if not audio_path:
        return [], "audio_extraction_failed"

    language = source_language if source_language in WHISPER_LANGUAGE_OPTIONS else "auto"
    source_json, source_status = run_whisper_json(audio_path, folder, "source_segments", language, False)
    translation_json, translation_status = run_whisper_json(audio_path, folder, "translated_source_segments", language, True)
    if not translation_json:
        return [], translation_status
    duration = probe_duration(source_video) or None
    segments = parse_whisper_segments(translation_json, duration, "english")
    source_segments = parse_whisper_segments(source_json, duration, "source_text") if source_json else []
    post_edit_report = []
    for segment in segments:
        segment["source_text"] = nearest_source_text(segment, source_segments)
        segment["source_language"] = language
        edited, edits = apply_translation_glossary(segment.get("source_text", ""), segment.get("english", ""))
        if edits:
            segment["raw_english"] = segment.get("english", "")
            segment["english"] = edited
            segment["translation_post_edits"] = edits
            post_edit_report.append(
                {
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                    "source_text": segment.get("source_text", ""),
                    "raw_english": segment.get("raw_english", ""),
                    "edited_english": edited,
                    "edits": edits,
                }
            )
    if not segments:
        return [], "empty_whisper_segment_translation"
    segments, llm_model, llm_edit_count = llm_post_edit_segments(segments, folder, level)
    save_json(folder / "segment_translation.json", segments)
    if source_segments:
        save_json(folder / "segment_source_transcript.json", source_segments)
    if post_edit_report:
        save_json(folder / "translation_post_edit_report.json", post_edit_report)
    (folder / "translated_source.txt").write_text(" ".join(segment["english"] for segment in segments), encoding="utf-8")
    engine = "local_whisper_cpp_auto_segment_translation" if language == "auto" else f"local_whisper_cpp_{language}_segment_translation"
    if post_edit_report:
        engine += "_with_glossary_post_edit"
    if llm_model and llm_edit_count:
        engine += f"_with_ollama_{slug(llm_model)}_post_edit"
    if source_status != "ok":
        engine += "_without_source_transcript"
    return segments, engine


def transcribe_uploaded_video(source_video: Path, folder: Path) -> tuple[str | None, str, str | None]:
    configured_transcript = run_local_text_command("WHISPER_CMD", "", folder / "transcript_zh.txt", source_video)
    if configured_transcript:
        return re.sub(r"\s+", " ", configured_transcript.strip())[:2400], "configured_local_whisper", None
    transcript, engine, translated = transcribe_with_whisper_cpp(source_video, folder)
    if transcript:
        return transcript[:2400], engine, translated[:2400] if translated else None
    return None, engine, None


def translate_chinese_source_text(
    source_text: str,
    topic: str,
    template: dict,
    folder: Path | None = None,
    source_video: Path | None = None,
    pretranslated_english: str | None = None,
) -> tuple[str, str]:
    if pretranslated_english:
        clean_translation = re.sub(r"\s+", " ", pretranslated_english).strip()
        if clean_translation:
            edited, edits = apply_translation_glossary(source_text, clean_translation)
            engine = "local_whisper_cpp_translation_to_english"
            if edits:
                engine += "_with_glossary_post_edit"
            return edited, engine
    if folder:
        configured = run_local_text_command("TRANSLATE_CMD", source_text, folder / "translated_source.txt", source_video)
        if configured:
            edited, edits = apply_translation_glossary(source_text, configured)
            engine = "configured_local_translation"
            if edits:
                engine += "_with_glossary_post_edit"
            return edited, engine

    text = re.sub(r"\s+", " ", source_text or "").strip()
    if not text:
        return (
            f"The video is about {topic or template['title']}. Students can watch it, notice one idea, give one reason, and ask one question in English.",
            "topic_only_no_transcript",
        )
    if not re.search(r"[\u4e00-\u9fff]", text):
        return (
            f"The source video says: {text}. Students can describe the key idea, explain why it matters, and ask one question in English.",
            "english_or_mixed_source_text",
        )

    sentences = [item.strip(" ，。！？!?") for item in re.split(r"[。！？!?]\s*", text) if item.strip()]
    clauses: list[str] = []

    def add(sentence: str):
        if sentence and sentence not in clauses:
            clauses.append(sentence)

    for sentence in sentences:
        if any(word in sentence for word in ["朋友", "友谊"]):
            add("The video explains that friendship needs care and respect.")
        if any(word in sentence for word in ["倾听", "认真听", "听别人"]):
            add("Friends should listen carefully to each other.")
        if any(word in sentence for word in ["沟通", "交流"]):
            add("They can use calm words to communicate.")
        if any(word in sentence for word in ["问题", "矛盾", "冲突"]):
            add("When a problem happens, they should talk calmly and look for a fair solution.")
        if any(word in sentence for word in ["道歉", "原谅"]):
            add("They can apologise, forgive, and try again.")
        if any(word in sentence for word in ["家乡", "本地", "地方"]):
            add("The video introduces local life and hometown experiences.")
        if any(word in sentence for word in ["文化", "传统", "节日"]):
            add("It shows culture, traditions, and memories that people can share.")
        if any(word in sentence for word in ["网络", "手机", "上网", "短视频"]):
            add("The video talks about digital life and online choices.")
        if any(word in sentence for word in ["安全", "个人信息", "隐私"]):
            add("Students should protect personal information and stay safe online.")
        if any(word in sentence for word in ["健康", "饮食", "运动"]):
            add("The video connects daily habits with health.")
        if any(word in sentence for word in ["环境", "垃圾", "保护"]):
            add("The video shows why people should care for the environment.")

    if not clauses:
        add(f"The video shares an idea about {topic or template['title']}.")
        add("Students can describe what they see and connect it with their own experience.")

    add("After watching, students can say what they noticed, explain one reason, and ask one question in English.")
    return " ".join(clauses), "local_rule_based_translation"


def clean_machine_translation(text: str, max_words: int = 360) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", cleaned) if item.strip()]
    output = []
    seen = set()
    word_count = 0
    for sentence in sentences:
        normalised = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        words = sentence.split()
        if word_count + len(words) > max_words:
            remaining = max_words - word_count
            if remaining >= 8:
                output.append(" ".join(words[:remaining]).rstrip(" ,;:") + ".")
            break
        output.append(sentence)
        word_count += len(words)
    return " ".join(output).strip() or cleaned


def load_translation_glossary() -> dict:
    configured = load_json(TRANSLATION_GLOSSARY_FILE, {})
    glossary = {
        "source_terms": list(DEFAULT_TRANSLATION_GLOSSARY["source_terms"]),
        "english_post_edits": list(DEFAULT_TRANSLATION_GLOSSARY["english_post_edits"]),
    }
    for key in ("source_terms", "english_post_edits"):
        if isinstance(configured.get(key), list):
            glossary[key].extend(configured[key])
    return glossary


def source_has_any(source_text: str, terms: list[str] | str | None) -> bool:
    if not terms:
        return True
    if isinstance(terms, str):
        terms = [terms]
    return any(term and term in source_text for term in terms)


def looks_like_untranslated_pinyin(english_text: str) -> bool:
    lowered = english_text.lower()
    return bool(re.search(r"\bxiao\s*qi\b|\bxiaoqi\b|\b[a-z]{2,}\s+[a-z]{2,}\b", lowered)) and len(english_text.split()) <= 9


def apply_translation_glossary(source_text: str, english_text: str, append_missing_terms: bool = True) -> tuple[str, list[str]]:
    source = re.sub(r"\s+", " ", source_text or "").strip()
    edited = re.sub(r"\s+", " ", english_text or "").strip()
    changes: list[str] = []
    if not edited:
        return edited, changes

    glossary = load_translation_glossary()
    for entry in glossary.get("english_post_edits", []):
        when = entry.get("when_source_contains")
        if not source_has_any(source, when):
            continue
        pattern = entry.get("pattern")
        replacement = entry.get("replace")
        if not pattern or replacement is None:
            continue
        updated = re.sub(pattern, replacement, edited, flags=re.I)
        if updated != edited:
            edited = re.sub(r"\s+", " ", updated).strip()
            changes.append(f"pattern:{pattern}->{replacement}")

    for entry in glossary.get("source_terms", []):
        sources = entry.get("source") or []
        target = entry.get("target", "")
        sentence = entry.get("sentence", "")
        if not source_has_any(source, sources) or not target:
            continue
        if re.search(rf"\b{re.escape(target)}\b", edited, flags=re.I):
            continue
        if not append_missing_terms:
            continue
        if looks_like_untranslated_pinyin(edited) or len(edited.split()) <= 7:
            edited = sentence or f"The key idea is {target}."
        else:
            edited = f"{edited.rstrip(' .')}. The key idea is {target}."
        changes.append(f"source_term:{'/'.join(sources)}->{target}")

    edited = clean_machine_translation(edited, 60)
    return edited, changes


def source_duration_word_budget(source_video: Path | None) -> int:
    duration = probe_duration(source_video) if source_video else None
    if not duration:
        return 360
    return max(36, min(240, int(duration * 2.1)))


def english_script_from_uploaded_source(
    topic: str,
    source_text: str,
    filename: str,
    folder: Path | None = None,
    source_video: Path | None = None,
    pretranslated_english: str | None = None,
) -> tuple[str, str, str, str, str]:
    clean_topic = re.sub(r"\s+", " ", (topic or "").strip())[:90]
    clean_source = re.sub(r"\s+", " ", (source_text or "").strip())[:1200]
    detected = detect_learning_topic(f"{clean_topic} {clean_source} {filename}")
    template = DEFAULT_TOPICS.get(detected, DEFAULT_TOPICS["local-culture"])
    title = f"{template['title']} from My Video" if clean_topic == "" else f"{clean_topic[:60]} English Version"
    translated_source, translation_engine = translate_chinese_source_text(clean_source, clean_topic, template, folder, source_video, pretranslated_english)
    if pretranslated_english:
        translated_source = clean_machine_translation(translated_source, source_duration_word_budget(source_video))
    if folder:
        (folder / "translated_source.txt").write_text(translated_source, encoding="utf-8")
    if pretranslated_english:
        script = translated_source
    else:
        script = (
            f"This English version follows the original video content. "
            f"Topic: {clean_topic or template['title']}. "
            f"{translated_source}"
        )
    vocabulary = vocabulary_from_text(f"{clean_topic} {translated_source}", template["vocabulary"])
    return title, script, template["zh"], vocabulary, translation_engine


def write_segment_vtt_file(segments: list[dict], mode: str, folder: Path, filename: str, fallback_zh: str = "") -> Path:
    entries = []
    lines = ["WEBVTT\n"]
    for segment in segments:
        english = re.sub(r"\s+", " ", segment.get("adapted_english") or segment.get("english") or "").strip()
        if not english:
            continue
        start = float(segment["start"])
        end = float(segment["end"])
        source_text = re.sub(r"\s+", " ", segment.get("source_text") or "").strip()
        second_line = source_text or fallback_zh
        text = english if mode == "english" or not second_line else f"{english}\n{second_line}"
        entries.append({"start": round(start, 3), "end": round(end, 3), "english": english, "source_text": second_line if mode != "english" else ""})
        lines.append(f"{vtt_time(start)} --> {vtt_time(end)}\n{text}\n")
    path = folder / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    save_json(folder / f"{Path(filename).stem}_entries.json", entries)
    return path


def write_segment_vtt_bundle(segments: list[dict], subtitle_mode: str, zh: str, folder: Path) -> dict:
    english = write_segment_vtt_file(segments, "english", folder, "segment_subtitles_english.vtt", zh)
    bilingual = write_segment_vtt_file(segments, "bilingual", folder, "segment_subtitles_bilingual.vtt", zh)
    selected = bilingual if subtitle_mode == "bilingual" else english
    save_json(
        folder / "segment_subtitle_entries.json",
        {
            "english": rel_media(english),
            "bilingual": rel_media(bilingual),
            "selected": subtitle_mode if subtitle_mode in {"english", "bilingual"} else "english",
        },
    )
    return {"english": english, "bilingual": bilingual, "selected": selected}


def fit_segment_clip_to_slot(audio_path: Path, segment: dict, folder: Path, index: int) -> tuple[Path, dict]:
    report = {"index": index, "speed": 1.0, "engine": "natural_duration"}
    if not shutil.which("ffmpeg"):
        report["engine"] = "ffmpeg_missing_no_fit"
        return audio_path, report
    audio_duration = probe_duration(audio_path) or 0
    slot_duration = max(0.45, float(segment["end"]) - float(segment["start"]) - 0.06)
    report["audio_duration"] = round(audio_duration, 3)
    report["slot_duration"] = round(slot_duration, 3)
    if audio_duration <= 0:
        return audio_path, report
    if audio_duration <= slot_duration * 1.04:
        report["engine"] = "shorter_than_slot_left_natural"
        return audio_path, report
    speed = max(1.0, min(3.0, audio_duration / slot_duration))
    output_dir = folder / "segment_timeline_fit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"segment_{index:03d}.m4a"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-filter:a", atempo_chain(speed), "-c:a", "aac", "-b:a", "128k", str(output)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode == 0 and output.exists():
        report["speed"] = round(speed, 3)
        report["engine"] = "segment_atempo_fit"
        report["fitted_duration"] = round(probe_duration(output) or slot_duration, 3)
        return output, report
    (folder / f"segment_fit_{index:03d}_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
    report["engine"] = "segment_fit_failed_left_natural"
    return audio_path, report


def make_segment_aligned_audio(segments: list[dict], folder: Path, level: str, source_duration: float, voice_style: str = "expressive") -> tuple[Path, str, dict]:
    if not segments:
        raise RuntimeError("No translated speech segments are available.")
    texts = [segment.get("adapted_english") or segment.get("english") or "" for segment in segments]
    raw_paths, tts_engine = synthesize_tts_clips(texts, folder, level, "segment", voice_style)
    fitted_paths: list[Path] = []
    fit_report = []
    for index, (segment, raw_path) in enumerate(zip(segments, raw_paths)):
        fitted_path, report = fit_segment_clip_to_slot(raw_path, segment, folder, index)
        fitted_paths.append(fitted_path)
        fit_report.append(report)

    output = folder / "segment_aligned_narration.m4a"
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required for segment-aligned narration.")
    command = ["ffmpeg", "-y"]
    for path in fitted_paths:
        command.extend(["-i", str(path)])
    filter_parts = []
    labels = []
    duration = max(0.5, min(MAX_VIDEO_SECONDS, source_duration))
    for index, segment in enumerate(segments):
        delay_ms = max(0, int(float(segment["start"]) * 1000))
        label = f"a{index}"
        labels.append(label)
        filter_parts.append(
            f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={delay_ms}|{delay_ms},atrim=0:{duration:.3f}[{label}]"
        )
    joined = "".join(f"[{label}]" for label in labels)
    filter_parts.append(f"{joined}amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{duration:.3f}[aout]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(180, 8 * len(segments)), check=False)
    if result.returncode != 0 or not output.exists():
        (folder / "segment_audio_mix_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
        raise RuntimeError("Segment-aligned audio mixing failed.")
    report = {
        "segment_count": len(segments),
        "slot_fit": fit_report,
        "timeline_audio_duration": probe_duration(output) or duration,
        "sync_engine": "whisper_timestamp_segment_timeline",
    }
    save_json(folder / "segment_alignment_report.json", report)
    return output, tts_engine, report


def make_segment_aligned_video_from_source(
    folder: Path,
    source_video: Path,
    segments: list[dict],
    level: str,
    title: str,
    subtitle_mode: str,
    zh: str,
    mask_options: dict | None = None,
    voice_style: str = "expressive",
) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required for segment-aligned video generation.")
    source_duration = probe_duration(source_video) or max(float(segment["end"]) for segment in segments)
    duration = min(MAX_VIDEO_SECONDS, source_duration)
    aligned_segments: list[dict] = []
    for segment in segments:
        start = float(segment["start"])
        end = min(float(segment["end"]), duration)
        if end <= start:
            continue
        english = re.sub(r"\s+", " ", segment.get("english", "")).strip()
        adapted = adapt_script(english, level)
        aligned_segments.append({**segment, "start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3), "adapted_english": adapted})
    if not aligned_segments:
        raise RuntimeError("Whisper returned no usable translated segments.")
    save_json(folder / "segment_translation_adapted.json", aligned_segments)
    subtitle_paths = write_segment_vtt_bundle(aligned_segments, subtitle_mode, zh, folder)
    subtitle_overlays: list[dict] = []
    audio_path, tts_engine, alignment_report = make_segment_aligned_audio(aligned_segments, folder, level, duration, voice_style)
    output = folder / "learning_video.mp4"
    visual_filter = build_source_visual_filter(mask_options)
    command = ["ffmpeg", "-y", "-i", str(source_video), "-i", str(audio_path)]
    if subtitle_overlays:
        for overlay in subtitle_overlays:
            command.extend(["-loop", "1", "-i", str(overlay["path"])])
        filters = [f"[0:v]{visual_filter},format=rgba[v0]"]
        previous = "v0"
        for index, overlay in enumerate(subtitle_overlays):
            next_label = f"v{index + 1}"
            overlay_label = f"ov{index}"
            start = max(0.0, float(overlay["start"]))
            end = min(duration, float(overlay["end"]))
            filters.append(f"[{index + 2}:v]format=rgba,colorkey=0xff00ff:0.20:0.0[{overlay_label}]")
            filters.append(f"[{previous}][{overlay_label}]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[{next_label}]")
            previous = next_label
        filters.append(f"[{previous}]format=yuv420p[vout]")
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-map",
                "1:a:0",
            ]
        )
    else:
        command.extend(["-map", "0:v:0", "-map", "1:a:0", "-vf", f"{visual_filter},format=yuv420p"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            f"{duration:.2f}",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(300, int(duration) * 5), check=False)
    if result.returncode != 0 or not output.exists():
        (folder / "segment_video_composition_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
        raise RuntimeError("Segment-aligned video composition failed.")
    return {
        "video": rel_media(output),
        "subtitles_vtt": rel_media(subtitle_paths["selected"]),
        "subtitles": {
            "english": rel_media(subtitle_paths["english"]),
            "bilingual": rel_media(subtitle_paths["bilingual"]),
        },
        "audio_source": rel_media(audio_path),
        "source_video": rel_media(source_video),
        "tts_engine": tts_engine,
        "duration": probe_duration(output) or duration,
        "visual_source": "uploaded_video_masked_original_timeline",
        "audio_sync_engine": "segment_aligned_dubbing",
        "source_duration": source_duration,
        "segment_count": len(aligned_segments),
        "subtitles_burned_into_video": bool(subtitle_overlays),
        "subtitle_overlay_engine": "quicklook_svg_chromakey_segment_overlay" if subtitle_overlays else "external_vtt_segment_timestamps",
        "mask_options": mask_options or {},
        "alignment_report": alignment_report,
    }


def make_english_video_from_source(
    folder: Path,
    source_video: Path,
    script: str,
    level: str,
    title: str,
    subtitle_mode: str,
    zh: str,
    mask_options: dict | None = None,
) -> dict:
    if not shutil.which("ffmpeg"):
        return make_browser_playable_video(folder, script, level, title, subtitle_mode, zh)

    subtitle_paths, subtitle_duration = write_vtt_bundle(script, zh, subtitle_mode, folder)
    subtitle_path = subtitle_paths["selected"]
    subtitle_entries, _ = build_subtitle_entries(script, zh, subtitle_mode)
    subtitle_overlays = make_subtitle_overlay_images(subtitle_entries, folder)
    audio_path, tts_engine, audio_duration = make_narration(script, folder, level, subtitle_duration)
    source_duration = probe_duration(source_video) or 0
    target_duration = min(MAX_VIDEO_SECONDS, max(source_duration, 8.0))
    audio_path, audio_duration, sync_engine = fit_audio_to_duration(audio_path, audio_duration, target_duration, folder)
    duration = target_duration
    output = folder / "learning_video.mp4"

    if subtitle_overlays:
        command = ["ffmpeg", "-y"]
        if duration > source_duration + 0.5:
            command.extend(["-stream_loop", "-1"])
        command.extend(["-i", str(source_video), "-i", str(audio_path)])
        for overlay in subtitle_overlays:
            command.extend(["-loop", "1", "-i", str(overlay["path"])])
        visual_filter = build_source_visual_filter(mask_options)
        filters = [f"[0:v]{visual_filter},format=rgba[v0]"]
        previous = "v0"
        for index, overlay in enumerate(subtitle_overlays):
            next_label = f"v{index + 1}"
            overlay_label = f"ov{index}"
            start = max(0.0, float(overlay["start"]))
            end = min(duration, float(overlay["end"]))
            filters.append(f"[{index + 2}:v]format=rgba,colorkey=0xff00ff:0.20:0.0[{overlay_label}]")
            filters.append(f"[{previous}][{overlay_label}]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[{next_label}]")
            previous = next_label
        filters.append(f"[{previous}]format=yuv420p[vout]")
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-t",
                f"{duration:.2f}",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
    else:
        command = [
            "ffmpeg",
            "-y",
        ]
        if duration > source_duration + 0.5:
            command.extend(["-stream_loop", "-1"])
        command.extend(
            [
                "-i",
                str(source_video),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-vf",
                f"{build_source_visual_filter(mask_options)},format=yuv420p",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-t",
                f"{duration:.2f}",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output.exists():
        fallback = make_browser_playable_video(folder, script, level, title, subtitle_mode, zh)
        fallback["source_video_fallback_reason"] = result.stderr.strip()[-500:] or "source-video composition failed"
        return fallback
    return {
        "video": rel_media(output),
        "subtitles_vtt": rel_media(subtitle_path),
        "subtitles": {
            "english": rel_media(subtitle_paths["english"]),
            "bilingual": rel_media(subtitle_paths["bilingual"]),
        },
        "audio_source": rel_media(audio_path),
        "source_video": rel_media(source_video),
        "tts_engine": tts_engine,
        "duration": probe_duration(output) or duration,
        "visual_source": "uploaded_video_masked_and_timeline_aligned",
        "audio_sync_engine": sync_engine,
        "source_duration": source_duration,
        "subtitles_burned_into_video": bool(subtitle_overlays),
        "subtitle_overlay_engine": "quicklook_svg_chromakey_overlay" if subtitle_overlays else "external_vtt_only",
    }


def material_from_system1_output(
    *,
    title: str,
    topic: str,
    zh: str,
    script: str,
    level: str,
    subtitle_mode: str,
    vocabulary: str,
    artifacts: dict,
    mode: str,
    source: dict | None = None,
) -> dict:
    material_id = uuid.uuid4().hex[:12]
    folder = MATERIALS_DIR / material_id
    folder.mkdir(parents=True, exist_ok=True)
    adapted = adapt_script(script, level)
    (folder / "script.txt").write_text(script, encoding="utf-8")
    (folder / "adapted_script.txt").write_text(adapted, encoding="utf-8")
    for item in MATERIALS.values():
        item["current"] = False
    material = {
        "id": material_id,
        "title": title,
        "topic": topic,
        "zh_support": zh,
        "level": level,
        "subtitle_mode": subtitle_mode,
        "script": script,
        "adapted_script": adapted,
        "key_vocabulary": vocabulary,
        "created_by": f"student_system1_{mode}",
        "created_at": now_iso(),
        "current": True,
        "artifacts": artifacts,
        "system1": {
            "mode": mode,
            "source": source or {},
            "pipeline": [
                "source_video_or_topic",
                "safety_screening",
                "translation_or_english_script_generation",
                "educational_text_adaptation",
                "local_tts_narration",
                "subtitle_rendering",
                "mp4_generation",
                "vtt_subtitles",
            ],
        },
    }
    MATERIALS[material_id] = material
    save_materials()
    log_action("student", "system1_material_generated", {"material_id": material_id, "mode": mode, "title": title})
    return material


def generate_system1_topic_material(payload: dict) -> dict:
    material = generate_material_from_topic(payload, "student_system1_topic")
    material["system1"] = {
        "mode": "topic_to_english_video",
        "source": {"topic": payload.get("topic", "")},
        "pipeline": ["teacher_approved_topic_input", "english_script_generation", "educational_text_adaptation", "local_tts_narration", "mp4_generation", "vtt_subtitles"],
    }
    MATERIALS[material["id"]] = material
    save_materials()
    return material


def receive_system1_video_material(handler: BaseHTTPRequestHandler) -> dict:
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Expected multipart video upload.")
    if content_length <= 0:
        raise ValueError("Uploaded video is empty.")
    if content_length > MAX_STUDENT_UPLOAD_BYTES:
        raise ValueError("Uploaded video is larger than the local 5-minute converter limit. Please compress it or use a shorter file.")
    boundary = multipart_boundary(content_type)
    if not boundary:
        raise ValueError("Upload boundary is missing.")
    body = handler.rfile.read(content_length)
    fields, files = extract_multipart_form(body, boundary)
    original_filename, video_bytes = files.get("video", ("", b""))
    if not original_filename or not video_bytes:
        raise ValueError("No video file was uploaded.")
    original_filename = Path(original_filename).name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Please upload an MP4, M4V, MOV, or WebM video.")

    level = fields.get("level") if fields.get("level") in {"A1", "A2", "B1"} else "A2"
    voice_style = fields.get("voice_style") if fields.get("voice_style") in {"friendly", "calm", "bright", "expressive"} else "expressive"
    subtitle_mode = fields.get("subtitle_mode") if fields.get("subtitle_mode") in {"english", "bilingual"} else "english"
    source_language = fields.get("source_language") if fields.get("source_language") in WHISPER_LANGUAGE_OPTIONS else "auto"
    topic = re.sub(r"\s+", " ", fields.get("source_topic", "").strip())[:100]
    custom_mask = parse_custom_mask(fields.get("custom_mask", ""))
    mask_options = {
        "mask_top": truthy_field(fields.get("mask_top"), True),
        "mask_bottom": truthy_field(fields.get("mask_bottom"), True),
        "custom_mask": custom_mask,
    }

    material_id = uuid.uuid4().hex[:12]
    folder = MATERIALS_DIR / material_id
    folder.mkdir(parents=True, exist_ok=True)
    source_name = f"source_{slug(Path(original_filename).stem)[:50] or 'video'}{extension}"
    source_video = folder / source_name
    source_video.write_bytes(video_bytes)
    source_duration = probe_duration(source_video)
    if source_duration is not None and source_duration > MAX_VIDEO_SECONDS:
        raise ValueError(f"Uploaded video is {source_duration:.1f}s. System 1 is configured for videos up to 5 minutes.")

    manual_text = re.sub(r"\s+", " ", (fields.get("manual_transcript", "") or fields.get("source_summary", "")).strip())[:1800]
    source_text = manual_text
    transcript_engine = "manual_notes"
    whisper_translation = None
    segment_translations: list[dict] = []
    segment_translation_engine = ""
    if not source_text:
        segment_translations, segment_translation_engine = translated_segments_with_whisper_cpp(source_video, folder, source_language, level)
        if segment_translations:
            transcript_engine = segment_translation_engine
            whisper_translation = " ".join(segment["english"] for segment in segment_translations)
            source_text = whisper_translation
        else:
            transcript, transcript_engine, whisper_translation = transcribe_uploaded_video(source_video, folder)
            source_text = transcript or ""
    if not source_text:
        raise ValueError(
            "System 1 could not hear speech in this video yet. Check that the video has clear audio, choose the source language in Settings, or write notes/transcript in Settings."
        )
    findings = screen_text(f"{topic} {source_text} {whisper_translation or ''}", SAFETY_INPUT_RULES)
    if findings:
        raise ValueError("The uploaded video description needs teacher review before System 1 generation.")

    title, script, zh, vocabulary, translation_engine = english_script_from_uploaded_source(
        topic,
        source_text,
        original_filename,
        folder,
        source_video,
        whisper_translation,
    )
    if segment_translation_engine:
        translation_engine = segment_translation_engine
    adapted = adapt_script(script, level)
    if segment_translations and not manual_text:
        try:
            artifacts = make_segment_aligned_video_from_source(folder, source_video, segment_translations, level, title, subtitle_mode, zh, mask_options, voice_style)
        except RuntimeError as error:
            artifacts = make_english_video_from_source(folder, source_video, adapted, level, title, subtitle_mode, zh, mask_options)
            artifacts["segment_alignment_fallback_reason"] = str(error)
    else:
        artifacts = make_english_video_from_source(folder, source_video, adapted, level, title, subtitle_mode, zh, mask_options)
    (folder / "source_input.txt").write_text(source_text or topic or original_filename, encoding="utf-8")
    (folder / "script.txt").write_text(script, encoding="utf-8")
    (folder / "adapted_script.txt").write_text(adapted, encoding="utf-8")
    for item in MATERIALS.values():
        item["current"] = False
    material = {
        "id": material_id,
        "title": title,
        "topic": topic or detect_learning_topic(source_text or original_filename),
        "zh_support": zh,
        "level": level,
        "subtitle_mode": subtitle_mode,
        "script": script,
        "adapted_script": adapted,
        "key_vocabulary": vocabulary,
        "created_by": "student_system1_video",
        "created_at": now_iso(),
        "current": True,
        "artifacts": artifacts,
        "system1": {
            "mode": "uploaded_video_to_english_video",
            "source": {
                "original_filename": original_filename,
                "source_topic": topic,
                "source_language": source_language,
                "manual_transcript_or_summary": bool(manual_text),
                "transcript_engine": transcript_engine,
                "translation_engine": translation_engine,
                "automatic_whisper_translation": bool(whisper_translation),
                "segment_aligned_translation": bool(segment_translations),
                "segment_count": len(segment_translations),
                "source_video": rel_media(source_video),
                "mask_options": mask_options,
                "voice_style": voice_style,
            },
            "pipeline": [
                "uploaded_video",
                "local_whisper_segment_timestamps",
                "safety_screening",
                "segment_level_translation_to_english",
                "educational_text_adaptation",
                "local_neural_tts_per_segment",
                "original_timeline_audio_reinsertion",
                "source_title_or_subtitle_masking",
                "mp4_generation",
                "timestamped_english_vtt_subtitles",
            ],
        },
    }
    MATERIALS[material_id] = material
    save_materials()
    log_action("student", "system1_video_material_generated", {"material_id": material_id, "file": original_filename})
    return material


def make_tts_audio(payload: dict) -> dict:
    text = re.sub(r"\s+", " ", (payload.get("text") or "").strip())[:900]
    if not text:
        raise ValueError("TTS text is empty.")
    style = payload.get("style") if payload.get("style") in {"friendly", "calm", "bright", "expressive"} else "expressive"
    level = payload.get("level") if payload.get("level") in {"A1", "A2", "B1"} else "A2"
    audio_id = uuid.uuid4().hex[:12]
    folder = TTS_DIR / audio_id
    folder.mkdir(parents=True, exist_ok=True)
    m4a_path = folder / "tts.m4a"
    paths, engine = synthesize_chatbot_tts_clips([text], folder, level, f"tts_{style}", style)
    output = paths[0]
    codec = output.suffix.lstrip(".") or "audio"
    if shutil.which("ffmpeg"):
        conversion = subprocess.run(
            ["ffmpeg", "-y", "-i", str(output), "-c:a", "aac", "-b:a", "128k", str(m4a_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if conversion.returncode == 0 and m4a_path.exists():
            output = m4a_path
            codec = "aac"
    voice_label = "macOS high-quality English voice" if engine.startswith("macos_say") else "Piper fallback voice"
    return {"audio_url": rel_media(output), "engine": engine, "voice": voice_label, "style": style, "codec": codec}


def keyword_match(text_lower: str, keyword: str) -> bool:
    keyword_lower = keyword.lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9 '-]*", keyword_lower):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])", text_lower))
    return keyword_lower in text_lower


def screen_text(text: str, rules: dict[str, list[str]]) -> list[dict]:
    text_lower = (text or "").lower()
    findings = []
    for category, keywords in rules.items():
        matches = [keyword for keyword in keywords if keyword_match(text_lower, keyword)]
        if matches:
            findings.append({"category": category, "matches": sorted(set(matches))})
    return findings


def split_script(script: str, max_words: int = 9) -> list[str]:
    chunks = []
    for sentence in re.split(r"(?<=[.!?])\s+", script.strip()):
        words = sentence.split()
        for index in range(0, len(words), max_words):
            chunk = " ".join(words[index : index + max_words]).strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def srt_time(seconds: float) -> str:
    total = int(seconds * 1000)
    h = total // 3_600_000
    total %= 3_600_000
    m = total // 60_000
    total %= 60_000
    s = total // 1000
    ms = total % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(seconds: float) -> str:
    return srt_time(seconds).replace(",", ".")


def build_subtitle_entries(script: str, zh: str, mode: str) -> tuple[list[dict], float]:
    chunks = split_script(script)
    cursor = 0.8
    entries = []
    for chunk in chunks:
        duration = max(2.2, min(6.0, len(chunk.split()) * 0.48 + 1.2))
        entries.append(
            {
                "start": round(cursor, 2),
                "end": round(cursor + duration, 2),
                "english": chunk,
                "zh": zh if mode == "bilingual" else "",
            }
        )
        cursor += duration + 0.12
    return entries, min(MAX_VIDEO_SECONDS, cursor + 0.8)


def write_vtt(script: str, zh: str, mode: str, folder: Path) -> tuple[Path, float]:
    entries, duration = build_subtitle_entries(script, zh, mode)
    lines = ["WEBVTT\n"]
    for entry in entries:
        text = entry["english"] if not entry["zh"] else f"{entry['english']}\n{entry['zh']}"
        lines.append(f"{vtt_time(entry['start'])} --> {vtt_time(entry['end'])}\n{text}\n")
    path = folder / "subtitles.vtt"
    path.write_text("\n".join(lines), encoding="utf-8")
    save_json(folder / "subtitle_entries.json", entries)
    return path, duration


def write_vtt_named(script: str, zh: str, mode: str, folder: Path, filename: str) -> tuple[Path, float]:
    entries, duration = build_subtitle_entries(script, zh, mode)
    lines = ["WEBVTT\n"]
    for entry in entries:
        text = entry["english"] if not entry["zh"] else f"{entry['english']}\n{entry['zh']}"
        lines.append(f"{vtt_time(entry['start'])} --> {vtt_time(entry['end'])}\n{text}\n")
    path = folder / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    save_json(folder / f"{Path(filename).stem}_entries.json", entries)
    return path, duration


def write_vtt_bundle(script: str, zh: str, selected_mode: str, folder: Path, prefix: str = "subtitles") -> tuple[dict, float]:
    english_path, english_duration = write_vtt_named(script, zh, "english", folder, f"{prefix}_english.vtt")
    bilingual_path, bilingual_duration = write_vtt_named(script, zh, "bilingual", folder, f"{prefix}_bilingual.vtt")
    selected_path = bilingual_path if selected_mode == "bilingual" else english_path
    return {"english": english_path, "bilingual": bilingual_path, "selected": selected_path}, max(english_duration, bilingual_duration)


def wrap_subtitle_text(text: str, width: int, max_lines: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) <= max_lines:
        return lines
    joined_tail = " ".join(lines[max_lines - 1 :])
    clipped_tail = joined_tail[: max(0, width - 1)].rstrip() + "..."
    return lines[: max_lines - 1] + [clipped_tail]


def write_subtitle_overlay_svg(english: str, zh: str, path: Path) -> None:
    english_lines = wrap_subtitle_text(english, 38, 3) or ["..."]
    zh_lines = []
    if zh:
        zh_lines = textwrap.wrap(zh, width=14, break_long_words=True, break_on_hyphens=False)[:2]

    square_height = 1280
    crop_offset_y = (square_height - 720) / 2
    line_height = 56
    zh_line_height = 48
    gap = 10 if zh_lines else 0
    padding_x = 42
    padding_y = 26
    text_width = 980
    box_width = text_width + padding_x * 2
    content_height = len(english_lines) * line_height + len(zh_lines) * zh_line_height + gap
    box_height = content_height + padding_y * 2
    box_x = (1280 - box_width) / 2
    box_y_final = max(330, 720 - box_height - 58)
    box_y = crop_offset_y + box_y_final
    text_x = 640
    current_y = box_y + padding_y + 46

    english_spans = []
    for index, line in enumerate(english_lines):
        dy = "0" if index == 0 else str(line_height)
        english_spans.append(f'<tspan x="{text_x}" dy="{dy}">{html.escape(line)}</tspan>')

    zh_spans = []
    zh_y = current_y + (len(english_lines) - 1) * line_height + gap + 46
    for index, line in enumerate(zh_lines):
        dy = "0" if index == 0 else str(zh_line_height)
        zh_spans.append(f'<tspan x="{text_x}" dy="{dy}">{html.escape(line)}</tspan>')

    zh_block = (
        f'<text x="{text_x}" y="{zh_y:.1f}" font-family="PingFang SC, Hiragino Sans GB, Arial Unicode MS, Arial, sans-serif" '
        f'font-size="38" fill="#ffffff" text-anchor="middle">{"".join(zh_spans)}</text>'
        if zh_spans
        else ""
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1280" viewBox="0 0 1280 1280">
  <rect x="0" y="0" width="1280" height="1280" fill="#ff00ff"/>
  <rect x="{box_x:.1f}" y="{box_y:.1f}" width="{box_width:.1f}" height="{box_height:.1f}" fill="#555555" shape-rendering="crispEdges"/>
  <text x="{text_x}" y="{current_y:.1f}" font-family="Arial, Helvetica, PingFang SC, sans-serif" font-size="46" font-weight="700" fill="#ffffff" text-anchor="middle">{"".join(english_spans)}</text>
  {zh_block}
</svg>
'''
    path.write_text(svg, encoding="utf-8")


def render_subtitle_overlay_png(english: str, zh: str, output: Path) -> bool:
    if not shutil.which("qlmanage") or not shutil.which("sips"):
        return False
    svg_path = output.with_suffix(".svg")
    thumbnail_path = Path(f"{svg_path}.png")
    write_subtitle_overlay_svg(english, zh, svg_path)
    if thumbnail_path.exists():
        thumbnail_path.unlink()
    if output.exists():
        output.unlink()
    preview = subprocess.run(
        ["qlmanage", "-t", "-s", "1280", "-o", str(output.parent), str(svg_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if preview.returncode != 0 or not thumbnail_path.exists():
        (output.parent / "quicklook_overlay_error.log").write_text(preview.stderr or preview.stdout, encoding="utf-8")
        return False
    crop = subprocess.run(
        ["sips", "-c", "720", "1280", str(thumbnail_path), "--out", str(output)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if crop.returncode != 0 or not output.exists():
        (output.parent / "sips_overlay_error.log").write_text(crop.stderr or crop.stdout, encoding="utf-8")
        return False
    return True


def topic_keywords(vocabulary: str, topic: str) -> list[str]:
    words = []
    for item in re.split(r"[,;/]", vocabulary or ""):
        clean = re.sub(r"\s+", " ", item).strip()
        if clean and clean.lower() not in {word.lower() for word in words}:
            words.append(clean)
    if not words:
        for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", topic):
            if word.lower() not in {"this", "that", "with", "from"} and word.lower() not in {item.lower() for item in words}:
                words.append(word)
            if len(words) >= 4:
                break
    return words[:5] or ["idea", "reason", "example"]


def topic_scene_plan(title: str, topic: str, script: str, vocabulary: str, duration: float) -> list[dict]:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", script) if item.strip()]
    keywords = topic_keywords(vocabulary, topic)
    scene_text = sentences[0] if sentences else f"Let's discuss {title} in English."
    detail_text = " ".join(sentences[1:3]) if len(sentences) > 1 else "Use one reason and one example to build your idea."
    prompt_text = f"What is one idea about {title} that you can explain with a reason?"
    weights = [0.22, 0.32, 0.22, 0.24]
    usable_duration = max(12.0, duration)
    durations = [max(3.0, usable_duration * weight) for weight in weights]
    scale = usable_duration / sum(durations)
    durations = [round(item * scale, 2) for item in durations]
    return [
        {"type": "hook", "title": title, "subtitle": "Watch. Think. Speak.", "body": scene_text, "narration": scene_text, "keywords": keywords[:3], "duration": durations[0]},
        {"type": "idea", "title": "Main Idea", "subtitle": title, "body": detail_text, "narration": detail_text, "keywords": keywords[:4], "duration": durations[1]},
        {"type": "language", "title": "Useful English", "subtitle": "Try these words", "body": " / ".join(keywords), "narration": f"Useful English words are: {', '.join(keywords)}.", "keywords": keywords, "duration": durations[2]},
        {"type": "prompt", "title": "Your Turn", "subtitle": "Get ready to speak", "body": prompt_text, "narration": prompt_text, "keywords": ["I think...", "because...", "for example..."], "duration": durations[3]},
    ]


def write_topic_slide_svg(scene: dict, path: Path, index: int) -> None:
    palette = [
        ("#f7fbff", "#176b87", "#e8f4f8", "#10212b"),
        ("#fffaf2", "#b45309", "#fef3c7", "#1f2933"),
        ("#f6fff8", "#15803d", "#dcfce7", "#14251a"),
        ("#fbf7ff", "#6d28d9", "#ede9fe", "#171124"),
    ]
    bg, accent, soft, ink = palette[index % len(palette)]
    title_lines = wrap_subtitle_text(scene.get("title", ""), 24, 2)
    body_lines = wrap_subtitle_text(scene.get("body", ""), 34, 5)
    keyword_items = scene.get("keywords", [])[:5]
    title_spans = "".join(f'<tspan x="96" dy="{0 if idx == 0 else 64}">{html.escape(line)}</tspan>' for idx, line in enumerate(title_lines))
    body_spans = "".join(f'<tspan x="96" dy="{0 if idx == 0 else 42}">{html.escape(line)}</tspan>' for idx, line in enumerate(body_lines))
    chips = []
    x = 96
    y = 585
    for item in keyword_items:
        label = html.escape(str(item)[:28])
        width = max(130, min(300, 28 + len(label) * 13))
        chips.append(f'<rect x="{x}" y="{y}" width="{width}" height="50" rx="22" fill="{soft}" stroke="{accent}" stroke-width="2"/>')
        chips.append(f'<text x="{x + 24}" y="{y + 33}" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700" fill="{accent}">{label}</text>')
        x += width + 18
        if x > 1030:
            break
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{bg}"/>
  <rect x="0" y="0" width="18" height="720" fill="{accent}"/>
  <circle cx="1110" cy="140" r="82" fill="{soft}" stroke="{accent}" stroke-width="6"/>
  <circle cx="1182" cy="236" r="38" fill="{accent}" opacity="0.18"/>
  <text x="96" y="95" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="700" fill="{accent}">{html.escape(scene.get("subtitle", ""))}</text>
  <text x="96" y="190" font-family="Arial, Helvetica, sans-serif" font-size="54" font-weight="800" fill="{ink}">{title_spans}</text>
  <text x="96" y="345" font-family="Arial, Helvetica, sans-serif" font-size="29" font-weight="500" fill="{ink}">{body_spans}</text>
  {"".join(chips)}
</svg>
'''
    path.write_text(svg, encoding="utf-8")


def render_topic_slide_png(scene: dict, output: Path, index: int) -> bool:
    if not shutil.which("qlmanage") or not shutil.which("sips"):
        return False
    svg_path = output.with_suffix(".svg")
    thumbnail_path = Path(f"{svg_path}.png")
    write_topic_slide_svg(scene, svg_path, index)
    if thumbnail_path.exists():
        thumbnail_path.unlink()
    if output.exists():
        output.unlink()
    preview = subprocess.run(
        ["qlmanage", "-t", "-s", "1280", "-o", str(output.parent), str(svg_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if preview.returncode != 0 or not thumbnail_path.exists():
        (output.parent / "quicklook_topic_slide_error.log").write_text(preview.stderr or preview.stdout, encoding="utf-8")
        return False
    resized = subprocess.run(
        ["sips", "-z", "720", "1280", str(thumbnail_path), "--out", str(output)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if resized.returncode != 0 or not output.exists():
        (output.parent / "sips_topic_slide_error.log").write_text(resized.stderr or resized.stdout, encoding="utf-8")
        return False
    return True


def write_topic_scene_vtt_bundle(scenes: list[dict], selected_mode: str, zh: str, folder: Path) -> dict:
    paths = {}
    for mode in ("english", "bilingual"):
        lines = ["WEBVTT\n"]
        entries = []
        cursor = 0.0
        for scene in scenes:
            start = cursor
            end = cursor + float(scene.get("duration", 3.5))
            english = re.sub(r"\s+", " ", scene.get("narration") or scene.get("body") or "").strip()
            source_hint = zh if mode == "bilingual" and zh else ""
            text = english if not source_hint else f"{english}\n{source_hint}"
            lines.append(f"{vtt_time(start)} --> {vtt_time(end)}\n{text}\n")
            entries.append({"start": round(start, 3), "end": round(end, 3), "english": english, "zh": source_hint})
            cursor = end
        path = folder / f"topic_scene_subtitles_{mode}.vtt"
        path.write_text("\n".join(lines), encoding="utf-8")
        save_json(folder / f"topic_scene_subtitles_{mode}_entries.json", entries)
        paths[mode] = path
    paths["selected"] = paths["bilingual"] if selected_mode == "bilingual" else paths["english"]
    return paths


def concatenate_audio_clips(clips: list[Path], folder: Path, prefix: str) -> tuple[Path, float]:
    if not clips:
        raise RuntimeError("No audio clips to concatenate.")
    if len(clips) == 1:
        return clips[0], probe_duration(clips[0]) or 0
    command = ["ffmpeg", "-y"]
    for clip in clips:
        command.extend(["-i", str(clip)])
    joined = "".join(f"[{index}:a]" for index in range(len(clips)))
    output = folder / f"{prefix}_combined.m4a"
    command.extend(
        [
            "-filter_complex",
            f"{joined}concat=n={len(clips)}:v=0:a=1[aout]",
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(120, 30 * len(clips)), check=False)
    if result.returncode != 0 or not output.exists():
        (folder / f"{prefix}_audio_concat_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
        raise RuntimeError("Topic scene audio concatenation failed.")
    return output, probe_duration(output) or sum(probe_duration(clip) or 0 for clip in clips)


def make_topic_storyboard_video(folder: Path, script: str, level: str, title: str, subtitle_mode: str, zh: str, topic: str, vocabulary: str) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required for MP4 generation.")
    scenes = topic_scene_plan(title, topic, script, vocabulary, 28.0)
    scene_texts = [re.sub(r"\s+", " ", scene.get("narration") or scene.get("body") or "").strip() for scene in scenes]
    scene_audio_clips, tts_engine = synthesize_tts_clips(scene_texts, folder, level, "topic_scene", "expressive")
    for scene, clip in zip(scenes, scene_audio_clips):
        scene["duration"] = round(max(1.6, probe_duration(clip) or 2.8), 2)
    duration = min(MAX_VIDEO_SECONDS, sum(float(scene["duration"]) for scene in scenes))
    audio_path, audio_duration = concatenate_audio_clips(scene_audio_clips, folder, "topic_scene")
    subtitle_paths = write_topic_scene_vtt_bundle(scenes, subtitle_mode, zh, folder)
    subtitle_path = subtitle_paths["selected"]
    slide_dir = folder / "topic_slides"
    slide_dir.mkdir(parents=True, exist_ok=True)
    slide_paths = []
    for index, scene in enumerate(scenes):
        slide_path = slide_dir / f"slide_{index:02d}.png"
        if not render_topic_slide_png(scene, slide_path, index):
            return make_browser_playable_video(folder, script, level, title, subtitle_mode, zh)
        slide_paths.append(slide_path)

    command = ["ffmpeg", "-y"]
    for slide_path, scene in zip(slide_paths, scenes):
        command.extend(["-loop", "1", "-t", f"{scene['duration']:.2f}", "-i", str(slide_path)])
    command.extend(["-i", str(audio_path)])
    filters = []
    labels = []
    for index in range(len(slide_paths)):
        label = f"v{index}"
        labels.append(label)
        scene_duration = float(scenes[index].get("duration", 3.5))
        filters.append(f"[{index}:v]scale=1280:720,setsar=1,fade=t=in:st=0:d=0.25,fade=t=out:st={max(0, scene_duration - 0.25):.2f}:d=0.25,format=yuv420p[{label}]")
    filters.append(f"{''.join(f'[{label}]' for label in labels)}concat=n={len(labels)}:v=1:a=0[vout]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            f"{len(slide_paths)}:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            f"{min(duration, audio_duration):.2f}",
            "-movflags",
            "+faststart",
            str(folder / "learning_video.mp4"),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(120, int(duration) * 4), check=False)
    output = folder / "learning_video.mp4"
    if result.returncode != 0 or not output.exists():
        (folder / "topic_storyboard_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
        return make_browser_playable_video(folder, script, level, title, subtitle_mode, zh)
    save_json(folder / "topic_storyboard.json", scenes)
    return {
        "video": rel_media(output),
        "subtitles_vtt": rel_media(subtitle_path),
        "subtitles": {
            "english": rel_media(subtitle_paths["english"]),
            "bilingual": rel_media(subtitle_paths["bilingual"]),
        },
        "audio_source": rel_media(audio_path),
        "tts_engine": tts_engine,
        "duration": probe_duration(output) or min(duration, audio_duration),
        "visual_source": "local_storyboard_topic_slides_scene_synced",
        "storyboard": rel_media(folder / "topic_storyboard.json"),
    }


def make_subtitle_overlay_images(entries: list[dict], folder: Path) -> list[dict]:
    if not entries:
        return []
    if len(entries) > MAX_BURNED_SUBTITLE_OVERLAYS:
        (folder / "subtitle_overlay_mode.txt").write_text(
            f"External VTT subtitles used because {len(entries)} subtitle cues exceed the fast local burn-in limit of {MAX_BURNED_SUBTITLE_OVERLAYS}.\n",
            encoding="utf-8",
        )
        return []
    overlay_dir = folder / "subtitle_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlays = []
    for index, entry in enumerate(entries):
        english = re.sub(r"\s+", " ", entry.get("english", "")).strip()[:260]
        zh = re.sub(r"\s+", " ", entry.get("zh", "")).strip()[:120]
        if not english:
            continue
        output = overlay_dir / f"overlay_{index:03d}.png"
        if not render_subtitle_overlay_png(english, zh, output):
            return []
        overlays.append({"path": output, "start": float(entry["start"]), "end": float(entry["end"])})
    return overlays


def probe_duration(path: Path) -> float | None:
    if not shutil.which("ffprobe") or not path.exists():
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def make_silent_audio(path: Path, duration: float) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            f"{duration:.2f}",
            "-acodec",
            "pcm_s16le",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return path


def synthesize_piper_clips(texts: list[str], folder: Path, level: str, prefix: str, style: str = "expressive") -> tuple[list[Path], str] | None:
    if not texts or not piper_available():
        return None
    data_dir = piper_espeak_data_dir()
    if not data_dir:
        return None
    clip_dir = folder / f"{prefix}_piper_clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    items = []
    output_paths = []
    for index, text in enumerate(texts):
        output = clip_dir / f"{prefix}_{index:03d}.wav"
        output_paths.append(output)
        items.append({"text": re.sub(r"\s+", " ", text).strip() or " ", "path": str(output)})
    batch_path = folder / f"{prefix}_piper_batch.json"
    save_json(batch_path, items)
    script = r'''
import json
import sys
import wave
from pathlib import Path
from piper import PiperVoice, SynthesisConfig

model_path = Path(sys.argv[1])
espeak_data_dir = Path(sys.argv[2])
batch_path = Path(sys.argv[3])
level = sys.argv[4]
style = sys.argv[5]

voice = PiperVoice.load(model_path, espeak_data_dir=espeak_data_dir)
base_length = {"A1": 0.98, "A2": 0.90, "B1": 0.86}.get(level, 0.90)
style_config = {
    "calm": {"length": 1.06, "noise": 0.58, "noise_w": 0.68, "volume": 0.96},
    "friendly": {"length": 0.96, "noise": 0.66, "noise_w": 0.82, "volume": 1.0},
    "bright": {"length": 0.90, "noise": 0.72, "noise_w": 0.92, "volume": 1.03},
    "expressive": {"length": 0.88, "noise": 0.76, "noise_w": 1.02, "volume": 1.05},
}.get(style, {"length": 0.88, "noise": 0.76, "noise_w": 1.02, "volume": 1.05})
config = SynthesisConfig(
    length_scale=base_length * style_config["length"],
    noise_scale=style_config["noise"],
    noise_w_scale=style_config["noise_w"],
    normalize_audio=True,
    volume=style_config["volume"],
)

for item in json.loads(batch_path.read_text(encoding="utf-8")):
    out_path = Path(item["path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = item.get("text", " ").strip() or " "
    wav_file = wave.open(str(out_path), "wb")
    with wav_file:
        ready = False
        for chunk in voice.synthesize(text, config):
            if not ready:
                wav_file.setframerate(chunk.sample_rate)
                wav_file.setsampwidth(chunk.sample_width)
                wav_file.setnchannels(chunk.sample_channels)
                ready = True
            wav_file.writeframes(chunk.audio_int16_bytes)
'''
    result = subprocess.run(
        [str(PIPER_PYTHON), "-c", script, str(PIPER_MODEL), str(data_dir), str(batch_path), level, style],
        capture_output=True,
        text=True,
        timeout=max(120, 18 * len(texts)),
        check=False,
    )
    if result.returncode == 0 and all(path.exists() and path.stat().st_size > 0 for path in output_paths):
        return output_paths, f"piper_lessac_medium_neural_tts_{style}"
    (folder / f"{prefix}_piper_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
    return None


def synthesize_say_clips(texts: list[str], folder: Path, level: str, prefix: str, style: str = "expressive") -> tuple[list[Path], str]:
    clip_dir = folder / f"{prefix}_say_clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    rate = {
        "calm": {"A1": "145", "A2": "156", "B1": "168"},
        "friendly": {"A1": "152", "A2": "166", "B1": "178"},
        "bright": {"A1": "158", "A2": "172", "B1": "184"},
        "expressive": {"A1": "154", "A2": "170", "B1": "182"},
    }.get(style, {"A1": "154", "A2": "170", "B1": "182"}).get(level, "170")
    voices_by_style = {
        "calm": ["Samantha", "Karen", "Moira", "Daniel"],
        "friendly": ["Samantha", "Allison", "Karen", "Ava"],
        "bright": ["Ava", "Samantha", "Allison", "Zoe"],
        "expressive": ["Ava", "Samantha", "Allison", "Susan", "Karen"],
    }
    voices = voices_by_style.get(style, voices_by_style["expressive"])
    generated_any = False
    for index, text in enumerate(texts):
        text_path = clip_dir / f"{prefix}_{index:03d}.txt"
        output = clip_dir / f"{prefix}_{index:03d}.aiff"
        text_path.write_text(re.sub(r"\s+", " ", text).strip() or " ", encoding="utf-8")
        generated = False
        if shutil.which("say"):
            for voice in voices:
                result = subprocess.run(
                    ["say", "-v", voice, "-r", rate, "-o", str(output), "-f", str(text_path)],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
                    generated = True
                    generated_any = True
                    break
        if not generated:
            fallback_duration = max(0.9, min(8.0, len(text.split()) * 0.42 + 0.4))
            output = make_silent_audio(clip_dir / f"{prefix}_{index:03d}_silent.wav", fallback_duration)
        output_paths.append(output)
    engine = f"macos_say_high_quality_{style}" if generated_any else "silent_fallback"
    return output_paths, engine


def synthesize_tts_clips(texts: list[str], folder: Path, level: str, prefix: str, style: str = "expressive") -> tuple[list[Path], str]:
    piper = synthesize_piper_clips(texts, folder, level, prefix, style)
    if piper:
        return piper
    return synthesize_say_clips(texts, folder, level, prefix, style)


def synthesize_chatbot_tts_clips(texts: list[str], folder: Path, level: str, prefix: str, style: str = "expressive") -> tuple[list[Path], str]:
    if shutil.which("say"):
        say_paths, say_engine = synthesize_say_clips(texts, folder, level, prefix, style)
        if not say_engine.startswith("silent"):
            return say_paths, f"{say_engine}_chatbot_primary"
    piper = synthesize_piper_clips(texts, folder, level, prefix, style)
    if piper:
        paths, engine = piper
        return paths, f"{engine}_chatbot_fallback"
    return synthesize_say_clips(texts, folder, level, prefix, style)


def atempo_chain(speed: float) -> str:
    factors = []
    remaining = max(0.25, speed)
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(round(remaining, 3))
    return ",".join(f"atempo={factor}" for factor in factors)


def fit_audio_to_duration(audio_path: Path, audio_duration: float, target_duration: float, folder: Path) -> tuple[Path, float, str]:
    if not shutil.which("ffmpeg") or target_duration <= 0 or audio_duration <= 0:
        return audio_path, audio_duration, "not_adjusted"
    speed = audio_duration / target_duration
    if abs(audio_duration - target_duration) <= max(0.8, target_duration * 0.08):
        return audio_path, audio_duration, "already_close_to_source_timeline"
    if audio_duration < target_duration and speed < 0.60:
        return audio_path, audio_duration, "audio_shorter_than_source_no_slowdown"
    if speed < 0.65 or speed > 1.85:
        return audio_path, audio_duration, "not_adjusted_ratio_too_large"
    output = folder / "narration_timeline_fit.m4a"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-filter:a", atempo_chain(speed), "-c:a", "aac", "-b:a", "128k", str(output)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode == 0 and output.exists():
        return output, probe_duration(output) or target_duration, f"atempo_fit_to_source_{speed:.2f}x"
    (folder / "audio_sync_error.log").write_text(result.stderr or result.stdout, encoding="utf-8")
    return audio_path, audio_duration, "audio_sync_failed"


def make_narration(script: str, folder: Path, level: str, fallback_duration: float) -> tuple[Path, str, float]:
    text_path = folder / "narration.txt"
    text_path.write_text(script, encoding="utf-8")
    paths, engine = synthesize_tts_clips([script], folder, level, "narration", "expressive")
    audio_path = paths[0]
    return audio_path, engine, probe_duration(audio_path) or fallback_duration


def make_browser_playable_video(folder: Path, script: str, level: str, title: str, subtitle_mode: str, zh: str) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required for MP4 generation.")

    subtitle_paths, subtitle_duration = write_vtt_bundle(script, zh, subtitle_mode, folder)
    subtitle_path = subtitle_paths["selected"]
    audio_path, tts_engine, audio_duration = make_narration(script, folder, level, subtitle_duration)
    duration = min(MAX_VIDEO_SECONDS, max(audio_duration, subtitle_duration, 8.0))
    output = folder / "learning_video.mp4"

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x17202A:s=1280x720:r=25:d={duration:.2f}",
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-t",
        f"{duration:.2f}",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(result.stderr.strip()[-900:] or "Video generation failed.")
    return {
        "video": rel_media(output),
        "subtitles_vtt": rel_media(subtitle_path),
        "subtitles": {
            "english": rel_media(subtitle_paths["english"]),
            "bilingual": rel_media(subtitle_paths["bilingual"]),
        },
        "audio_source": rel_media(audio_path),
        "tts_engine": tts_engine,
        "duration": probe_duration(output) or duration,
    }


def open_topic_script(topic: str) -> tuple[str, str, str]:
    clean_topic = re.sub(r"\s+", " ", topic).strip()[:80] or "English Discussion"
    lowered = clean_topic.lower()
    if re.search(r"[\u4e00-\u9fff]", clean_topic):
        return (
            "Teacher Approved Topic",
            (
                "This English video introduces a teacher approved topic. Students can notice one important detail, explain what happens, "
                "and connect it with their own experience. A strong answer gives one clear reason and one short example."
            ),
            "idea, detail, reason, example, experience",
        )
    if any(word in lowered for word in ["hometown", "local", "culture", "tradition"]):
        return (
            clean_topic,
            (
                f"{clean_topic} is the way people remember and share a place. It can appear in food, festivals, buildings, stories, and everyday words. "
                "When students explain it in English, they can choose one detail, say where it comes from, and explain why people still care about it. "
                "A good discussion question is: how can young people keep local culture alive?"
            ),
            "hometown, culture, festival, memory, tradition",
        )
    if any(word in lowered for word in ["friend", "communication", "relationship"]):
        return (
            clean_topic,
            (
                f"{clean_topic} is about how people listen, speak, and solve problems together. A good friend does not only agree; a good friend also tries to understand. "
                "Students can describe one communication problem, explain one feeling, and suggest one kind action."
            ),
            "friendship, listen, feeling, respect, solution",
        )
    if any(word in lowered for word in ["online", "internet", "phone", "safety", "privacy"]):
        return (
            clean_topic,
            (
                f"{clean_topic} means making careful choices when using phones, games, videos, and social media. Students should protect private information, check sources, "
                "and ask a trusted adult when something feels unsafe. In discussion, they can explain one safe habit and one reason."
            ),
            "online safety, privacy, source, trusted adult, habit",
        )
    if any(word in lowered for word in ["environment", "rubbish", "climate", "recycle"]):
        return (
            clean_topic,
            (
                f"{clean_topic} connects small daily choices with the world around us. People can reduce waste, reuse useful things, and protect shared places. "
                "Students can describe one problem, one possible action, and one reason the action matters."
            ),
            "environment, waste, reuse, protect, action",
        )
    return (
        clean_topic,
        (
            f"{clean_topic} can become a real English discussion when students connect it with people, choices, and reasons. "
            "First, describe what the topic means. Next, give one example from life or a video. Then explain why the example matters. "
            "The goal is to speak clearly, listen to another idea, and build the discussion together."
        ),
        "meaning, choice, reason, example, discussion",
    )


def adapt_script(script: str, level: str) -> str:
    replacements = {
        "reliable": "trustworthy",
        "significant": "important",
        "approximately": "about",
        "communicative": "communication",
    }
    output = script
    for hard, easy in replacements.items():
        output = re.sub(rf"\b{hard}\b", easy, output, flags=re.I)
    limit = {"A1": 12, "A2": 24, "B1": 30}.get(level, 24)
    sentences = []
    for raw in re.split(r"(?<=[.!?])\s+", output.strip()):
        words = raw.split()
        if len(words) <= limit:
            sentences.append(raw)
        else:
            for idx in range(0, len(words), limit):
                part = " ".join(words[idx : idx + limit]).strip(" ,.;")
                if part:
                    sentences.append(part + ".")
    return " ".join(sentences)


def generate_material_from_topic(payload: dict, role: str) -> dict:
    topic = (payload.get("topic") or "online-safety").strip()
    level = payload.get("level") if payload.get("level") in {"A1", "A2", "B1"} else "A2"
    subtitle_mode = payload.get("subtitle_mode") if payload.get("subtitle_mode") in {"english", "bilingual"} else "english"
    template = DEFAULT_TOPICS.get(topic.lower()) or next((item for item in DEFAULT_TOPICS.values() if item["title"].lower() == topic.lower()), None)
    if template:
        title = template["title"]
        zh = template["zh"]
        script = template["script"]
        vocabulary = template["vocabulary"]
    else:
        title, script, vocabulary = open_topic_script(topic)
        zh = topic

    adapted = adapt_script(script, level)
    material_id = uuid.uuid4().hex[:12]
    folder = MATERIALS_DIR / material_id
    folder.mkdir(parents=True, exist_ok=True)
    artifacts = make_topic_storyboard_video(folder, adapted, level, title, subtitle_mode, zh, topic, vocabulary)
    (folder / "script.txt").write_text(script, encoding="utf-8")
    (folder / "adapted_script.txt").write_text(adapted, encoding="utf-8")

    material = {
        "id": material_id,
        "title": title,
        "topic": topic,
        "zh_support": zh,
        "level": level,
        "subtitle_mode": subtitle_mode,
        "script": script,
        "adapted_script": adapted,
        "key_vocabulary": vocabulary,
        "created_by": role,
        "created_at": now_iso(),
        "current": True,
        "artifacts": artifacts,
    }
    for item in MATERIALS.values():
        item["current"] = False
    MATERIALS[material_id] = material
    save_materials()
    log_action(role, "material_generated", {"material_id": material_id, "title": title})
    return material


def current_material() -> dict | None:
    current = [item for item in MATERIALS.values() if item.get("current")]
    if current:
        return sorted(current, key=lambda item: item["created_at"], reverse=True)[0]
    if MATERIALS:
        return sorted(MATERIALS.values(), key=lambda item: item["created_at"], reverse=True)[0]
    return None


def ensure_demo_material() -> dict:
    material = current_material()
    if material:
        return material
    return generate_material_from_topic({"topic": "online-safety", "level": "A2", "subtitle_mode": "bilingual"}, "system")


def estimate_english_ratio(text: str) -> float:
    letters = sum(1 for char in text if char.isalpha())
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    total = letters + chinese
    return 0.0 if total == 0 else letters / total


def reasoning_count(text: str) -> int:
    text_lower = text.lower()
    return sum(1 for marker in REASONING_MARKERS if marker in text_lower)


def wants_clarification(text: str) -> bool:
    text_lower = text.lower()
    return any(marker in text_lower for marker in CLARIFICATION_MARKERS)


def is_stuck_expression(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(i\s+do\s+not\s+know|i\s+don't\s+know|no\s+idea|not\s+sure|i\s+can't|i\s+cannot)\b", lowered))


def focus_phrase(text: str) -> str:
    lowered = text.lower()
    for phrase in ["personal information", "online safety", "trusted adult", "local culture", "friendship", "reliable information"]:
        if phrase in lowered:
            return phrase
    stop_words = {
        "what",
        "does",
        "mean",
        "explain",
        "because",
        "think",
        "people",
        "person",
        "should",
        "some",
        "someone",
        "really",
        "interesting",
        "this",
        "that",
        "there",
        "their",
        "about",
        "maybe",
        "may",
        "like",
        "want",
        "would",
        "could",
        "good",
        "very",
    }
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)
        if word.lower() not in stop_words
    ]
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    if words:
        return " ".join(words[:3])
    if chinese:
        return chinese[0]
    return "your idea"


def student_idea_reference(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "your idea"
    replacements = [
        (r"\bsome\s+someone\b", "some people"),
        (r"\bsomeone\s+may\s+like\s+think\b", "someone may think"),
        (r"\bsome\s+people\s+may\s+like\s+think\b", "some people may think"),
        (r"\bmay\s+like\s+think\b", "may think"),
        (r"\blike\s+think\b", "think"),
        (r"\bthis\s+is\s+because\s+you\s+are\b", "this is because they are"),
        (r"\bi\s+think\s+this\s+is\s+because\b", "I think this because"),
    ]
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:")
    if len(cleaned) > 120:
        cleaned = cleaned[:117].rsplit(" ", 1)[0] + "..."
    return cleaned or "your idea"


def classroom_language_feedback(text: str) -> str | None:
    lowered = text.lower()
    if any(word in lowered for word in ["stupid", "idiot", "dumb"]):
        return 'Let\'s use respectful classroom English. A safer sentence is: "I disagree because..."'
    return None


def response_preface(student_text: str) -> str:
    idea = student_idea_reference(student_text)
    original = re.sub(r"\s+", " ", student_text.strip())
    if idea and idea.lower() != original.lower():
        return f'I heard your idea. A clearer sentence is: "{idea}."'
    return f'I heard your idea: "{idea}."'


def choose_dialogue_variant(session: dict, key: str, salt: str = "") -> str:
    options = DIALOGUE_VARIANTS.get(key) or DIALOGUE_VARIANTS["IBI"]
    turn = session.get("dialogue_state", {}).get("turn_count", 0)
    history = "|".join(session.get("dialogue_state", {}).get("move_sequence", [])[-5:])
    seed = f"{session.get('id', '')}:{turn}:{key}:{salt}:{history}"
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(options)
    return options[index]


def response_acknowledgement(session: dict, student_text: str, move: str) -> str:
    state = session.get("dialogue_state", {})
    words = len(student_text.split())
    if move == "MS" or words <= 4:
        return choose_dialogue_variant(session, "MS", "ack").split(".")[0] + "."
    if state.get("reasoning_depth") == "high":
        return "Strong reasoning."
    return choose_dialogue_variant(session, "ack", student_text[:20])


def one_question_response(session: dict, student_text: str, move: str) -> str:
    question = choose_dialogue_variant(session, move, student_text[:40])
    focus = focus_phrase(student_text)
    if focus != "your idea" and move in {"EOR", "BI", "CH"} and len(focus.split()) <= 3:
        question = question.replace("that view", f"the idea about {focus}")
        question = question.replace("this idea", f"the idea about {focus}")
    question = re.sub(r"\s+", " ", question).strip()
    if question.count("?") > 1:
        first, *_ = question.split("?")
        question = first.strip() + "?"
    return question


def update_dialogue_state(session: dict, student_text: str) -> dict:
    turns = session.get("turns", [])
    last_words = len(student_text.split())
    markers = reasoning_count(student_text)
    participation = "emerging"
    if last_words >= 18:
        participation = "active"
    elif last_words >= 8:
        participation = "developing"
    reasoning_depth = "low"
    if markers >= 2:
        reasoning_depth = "high"
    elif markers == 1 or last_words >= 16:
        reasoning_depth = "medium"
    state = session["dialogue_state"]
    state.update(
        {
            "turn_count": len(turns) + 1,
            "participation_level": participation,
            "reasoning_depth": reasoning_depth,
            "reasoning_marker_count": state.get("reasoning_marker_count", 0) + markers,
            "last_response_words": last_words,
            "last_english_ratio": round(estimate_english_ratio(student_text), 2),
        }
    )
    return state


def select_move(session: dict, text: str, input_findings: list[dict]) -> tuple[str, str]:
    state = session["dialogue_state"]
    turn = state.get("turn_count", 1)
    recent = state.get("move_sequence", [])[-2:]
    if input_findings:
        return "MS", "autonomy_support"
    if wants_clarification(text):
        return "VB", "vocabulary_bridge"
    if is_stuck_expression(text):
        return "MS", "autonomy_support"
    if turn == 1:
        return "IBI", "elaboration_invitation"
    if turn % 6 == 0:
        return "C", "synthesis_prompt"
    if state.get("participation_level") == "emerging" and "MS" not in recent:
        return "MS", "autonomy_support"
    if state.get("reasoning_depth") == "low":
        return "EOR", "reasoning_prompt"
    if state.get("reasoning_depth") == "high" and "CH" not in state.get("move_sequence", [])[-4:]:
        return "CH", "perspective_shift"
    if turn % 4 == 0:
        return "RD", "metacognitive_prompt"
    return "BI", "example_invitation"


def chatbot_response(session: dict, student_text: str, move: str, scaffold: str, input_findings: list[dict]) -> str:
    material = MATERIALS.get(session.get("material_id", "")) or current_material() or {}
    focus = focus_phrase(student_text)
    classroom_feedback = classroom_language_feedback(student_text)
    if input_findings:
        return "Thank you for telling me. Please pause and tell your teacher now. We can continue learning when it feels safe."
    if classroom_feedback:
        return f"{classroom_feedback} What respectful reason can you give about {material.get('title', 'the video idea')}?"
    if wants_clarification(student_text):
        if "reliable" in student_text.lower():
            return "Reliable means you can trust something. For example, reliable information has a clear source or clear proof. Can you make one sentence with reliable?"
        return f"Let's make it simpler. You can say: I want to understand {focus}. What short sentence can you try?"

    question = one_question_response(session, student_text, move)
    if move == "C":
        question = question.replace("your main ideas", f"your main ideas about {material.get('title', 'the topic')}")
    return question


SYSTEM2_BANNED_GENERIC_PHRASES = (
    "good start",
    "nice thinking",
    "it does not need to be perfect",
    "let's start with one useful word",
    "what word do you need",
    "take your time",
    "can you connect the idea about",
)


def dialogue_content_words(text: str) -> list[str]:
    stop_words = {
        "the",
        "a",
        "an",
        "to",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "it",
        "this",
        "that",
        "you",
        "your",
        "can",
        "could",
        "would",
        "should",
        "what",
        "why",
        "how",
        "when",
        "where",
        "with",
        "from",
        "about",
        "because",
        "think",
        "idea",
        "video",
        "maybe",
        "may",
        "might",
        "he",
        "she",
        "they",
        "them",
        "his",
        "her",
        "him",
        "feel",
        "feels",
    }
    return [word for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower()) if word not in stop_words]


def lexical_overlap_ratio(source: str, response: str) -> float:
    source_words = set(dialogue_content_words(source))
    response_words = set(dialogue_content_words(response))
    if not source_words or not response_words:
        return 0.0
    return len(source_words & response_words) / max(1, min(len(source_words), len(response_words)))


def learner_dialogue_situation(session: dict, student_text: str, input_findings: list[dict]) -> str:
    if input_findings:
        return "safeguarding_support"
    words = len(student_text.split())
    if classroom_language_feedback(student_text):
        return "respectful_language_repair"
    if wants_clarification(student_text):
        return "vocabulary_or_meaning_help"
    if is_stuck_expression(student_text):
        return "stuck_or_low_confidence"
    if words <= 4:
        return "short_fragment_needs_extension"
    if reasoning_count(student_text) >= 2 or words >= 18:
        return "active_reasoning"
    if reasoning_count(student_text) == 1 or words >= 10:
        return "developing_reasoning"
    return "emerging_idea"


def recent_dialogue_context(session: dict, limit: int = 4) -> list[dict]:
    context = []
    for turn in session.get("turns", [])[-limit:]:
        context.append(
            {
                "student": turn.get("student_text", "")[:220],
                "ai": turn.get("ai_response", "")[:220],
                "move": turn.get("move", ""),
            }
        )
    return context


def parse_llm_dialogue_response(output: str) -> str:
    parsed = extract_json_array(output)
    text = ""
    if isinstance(parsed, list) and parsed:
        item = parsed[0]
        if isinstance(item, dict):
            text = str(item.get("response") or item.get("ai_response") or item.get("text") or "")
    if not text:
        text = output or ""
    text = re.sub(r"\s+", " ", text).strip().strip("\"'")
    text = re.sub(r"^(AI|Assistant|Tutor)\s*:\s*", "", text, flags=re.I).strip()
    text = re.sub(r"\s*\[[^\]]+\]\s*", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    if parts and parts[0].strip():
        text = parts[0].strip()
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in ".!?":
        text += "?"
    return text


def valid_llm_dialogue_response(response: str, student_text: str, recent_ai: list[str]) -> bool:
    if not response:
        return False
    lowered = response.lower()
    student_clean = re.sub(r"[^a-z0-9' ]+", "", student_text.lower()).strip()
    response_clean = re.sub(r"[^a-z0-9' ]+", "", lowered).strip()
    if student_clean and len(student_clean.split()) <= 4 and student_clean in response_clean:
        return False
    student_content = set(dialogue_content_words(student_text))
    response_content = set(dialogue_content_words(response))
    if 1 <= len(student_content) <= 3 and student_content and len(student_content & response_content) / len(student_content) >= 0.8:
        return False
    if any(phrase in lowered for phrase in SYSTEM2_BANNED_GENERIC_PHRASES):
        return False
    if len(response.split()) < 5 or len(response.split()) > 24:
        return False
    if response.count("?") > 1:
        return False
    if lexical_overlap_ratio(student_text, response) >= 0.72 and len(dialogue_content_words(student_text)) >= 3:
        return False
    for previous in recent_ai[-3:]:
        if previous and lexical_overlap_ratio(previous, response) >= 0.72:
            return False
    return True


def llm_chatbot_response(session: dict, student_text: str, move: str, scaffold: str, input_findings: list[dict]) -> tuple[str | None, str | None]:
    if input_findings:
        return None, None
    model = ollama_available_model("dialogue")
    if not model:
        return None, None
    material = MATERIALS.get(session.get("material_id", "")) or current_material() or {}
    state = session.get("dialogue_state", {})
    situation = learner_dialogue_situation(session, student_text, input_findings)
    recent_context = recent_dialogue_context(session)
    recent_ai = [item.get("ai", "") for item in recent_context]
    prompt_payload = {
        "material_title": material.get("title", session.get("material_title", "the English video")),
        "topic": material.get("topic", session.get("topic", "English discussion")),
        "level": session.get("level", "A2"),
        "student_task": session.get("student_task", ""),
        "student_text": student_text,
        "selected_move": move,
        "move_name": TECH_SEDA_MOVES.get(move, move),
        "scaffold": scaffold,
        "learner_state": {
            "situation": situation,
            "participation_level": state.get("participation_level"),
            "reasoning_depth": state.get("reasoning_depth"),
            "last_response_words": state.get("last_response_words"),
            "turn_count": state.get("turn_count"),
        },
        "recent_dialogue": recent_context,
    }
    prompt = (
        "You are System 2 in a local English-learning research platform: a warm, intelligent, dialogic speaking partner.\n"
        "Use the selected Tech-SEDA move, but do not sound like a template.\n"
        "Return ONLY valid JSON: {\"response\":\"one natural spoken English sentence\"}.\n"
        "Strict rules:\n"
        "- exactly one sentence, 5 to 24 words;\n"
        "- ask one concrete next question OR offer one concrete sentence starter;\n"
        "- do not repeat the student's wording;\n"
        "- do not start with generic praise;\n"
        "- do not use these phrases: Good start, Nice thinking, Take your time, It does not need to be perfect, useful word;\n"
        "- adapt to confidence, response length, reasoning depth, and recent dialogue;\n"
        "- if the learner is stuck, give a small choice tied to the video;\n"
        "- if the learner gives an unfinished fragment, do not quote it; ask for one scene, person, or action;\n"
        "- if the learner gives a reason, ask for evidence, an example, or another viewpoint;\n"
        "- keep language suitable for the learner level.\n"
        f"Input JSON:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    timeout = int(os.getenv("SYSTEM2_LLM_TIMEOUT", "35") or "35")
    output, error = run_ollama_prompt(model, prompt, timeout, temperature=0.62, top_p=0.9, num_predict=90)
    if error or not output:
        return None, None
    response = parse_llm_dialogue_response(output)
    if not valid_llm_dialogue_response(response, student_text, recent_ai):
        avoid_words = ", ".join(sorted(set(dialogue_content_words(student_text)))[:5]) or "none"
        retry_prompt = (
            "Return ONLY valid JSON: {\"response\":\"one natural spoken English sentence\"}.\n"
            "The previous response was rejected because it sounded too generic, repeated wording, or was not one sentence.\n"
            "Make a fresh one-sentence reply for a spoken English learner.\n"
            "Rules: 5 to 18 words, no praise phrase, no repetition of the student's words, one concrete next step tied to the video.\n"
            f"Do not use these student content words: {avoid_words}.\n"
            "For an unfinished fragment, ask for one scene, person, or action without quoting the fragment.\n"
            f"Student situation: {situation}. Tech-SEDA move: {move} - {TECH_SEDA_MOVES.get(move, move)}.\n"
            f"Video title/topic: {material.get('title', session.get('material_title', 'the English video'))} / {material.get('topic', session.get('topic', 'English discussion'))}.\n"
            f"Student said: {student_text}"
        )
        output, error = run_ollama_prompt(model, retry_prompt, min(timeout, 24), temperature=0.72, top_p=0.92, num_predict=70)
        if error or not output:
            return None, None
        response = parse_llm_dialogue_response(output)
        if not valid_llm_dialogue_response(response, student_text, recent_ai):
            return None, None
    return response, f"ollama_{model.replace(':', '-')}_dialogic_engine"


def generate_chatbot_response(session: dict, student_text: str, move: str, scaffold: str, input_findings: list[dict]) -> tuple[str, str]:
    llm_response, engine = llm_chatbot_response(session, student_text, move, scaffold, input_findings)
    if llm_response and engine:
        return llm_response, engine
    return chatbot_response(session, student_text, move, scaffold, input_findings), "local_rule_based_safety_fallback"


def filter_ai_output(text: str) -> tuple[str, list[dict], bool]:
    findings = screen_text(text, SAFETY_OUTPUT_RULES)
    if estimate_english_ratio(text) < 0.5:
        findings.append({"category": "non_english_output", "matches": ["english_ratio_low"]})
    if findings:
        return "Let's keep this safe and focused on English learning. Please share one simple idea or ask for one English word.", findings, True
    return text, [], False


def create_session(payload: dict) -> dict:
    material = MATERIALS.get(payload.get("material_id", "")) or ensure_demo_material()
    session_id = uuid.uuid4().hex[:12]
    participant_code = sanitize_code(payload.get("participant_code", ""))
    level = payload.get("level") if payload.get("level") in {"A1", "A2", "B1"} else material.get("level", "A2")
    student_task = re.sub(r"\s+", " ", (payload.get("student_task") or "").strip())[:700]
    student_video_upload = clean_upload_metadata(payload.get("student_video_upload"))
    voice_profile = payload.get("voice_profile") if payload.get("voice_profile") in {"friendly", "calm", "bright", "expressive"} else "expressive"
    session = {
        "id": session_id,
        "status": "active",
        "chatbot_listening": bool(payload.get("chatbot_listening", True)),
        "participant_code": participant_code,
        "participant_hash": participant_hash(participant_code),
        "material_id": material["id"],
        "material_title": material["title"],
        "topic": material["topic"],
        "level": level,
        "student_task": student_task,
        "student_video_upload": student_video_upload,
        "system1_material": material.get("system1"),
        "lesson_context": payload.get("lesson_context") if isinstance(payload.get("lesson_context"), dict) else current_lesson_context(),
        "voice_profile": voice_profile,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "dialogue_state": {
            "current_topic": material["topic"],
            "estimated_english_proficiency_level": level,
            "turn_count": 0,
            "participation_level": "not_started",
            "reasoning_depth": "not_started",
            "reasoning_marker_count": 0,
            "move_sequence": [],
            "scaffold_sequence": [],
        },
        "flags": [],
        "turns": [],
        "teacher_actions": [],
        "teacher_notes": [],
    }
    SESSIONS[session_id] = session
    sync_student_account_from_session(session, save=False)
    save_sessions()
    save_student_accounts()
    save_json(SESSIONS_DIR / f"{session_id}.json", session)
    return session


def save_session(session: dict) -> None:
    session["updated_at"] = now_iso()
    SESSIONS[session["id"]] = session
    sync_student_account_from_session(session, save=False)
    save_sessions()
    save_student_accounts()
    save_json(SESSIONS_DIR / f"{session['id']}.json", session)


def add_turn(session: dict, payload: dict) -> dict:
    if session["status"] != "active":
        raise ValueError("This session is not active.")
    if not session.get("chatbot_listening", True):
        raise ValueError("The chatbot is currently stopped for this student session.")
    if len(session.get("turns", [])) >= MAX_TURNS:
        raise ValueError("Maximum turn limit reached.")
    student_text = re.sub(r"\s+", " ", (payload.get("student_text") or "").strip())[:1200]
    if not student_text:
        raise ValueError("Student text is empty.")

    input_findings = screen_text(student_text, SAFETY_INPUT_RULES)
    if input_findings:
        session["flags"].append({"time": now_iso(), "turn": len(session["turns"]) + 1, "type": "input_safeguarding", "findings": input_findings})
    state = update_dialogue_state(session, student_text)
    move, scaffold = select_move(session, student_text, input_findings)
    raw, generation_engine = generate_chatbot_response(session, student_text, move, scaffold, input_findings)
    ai_response, output_findings, substituted = filter_ai_output(raw)
    state["move_sequence"] = (state.get("move_sequence", []) + [move])[-MAX_TURNS:]
    state["scaffold_sequence"] = (state.get("scaffold_sequence", []) + [scaffold])[-MAX_TURNS:]
    turn = {
        "turn": len(session["turns"]) + 1,
        "timestamp": now_iso(),
        "input_mode": payload.get("input_mode", "typed"),
        "student_text": student_text,
        "ai_response": ai_response,
        "move": move,
        "move_name": TECH_SEDA_MOVES[move],
        "scaffold": scaffold,
        "heuristic_elaboration_indicators": {
            "reasoning_depth": state["reasoning_depth"],
            "last_reasoning_markers": reasoning_count(student_text),
            "reasoning_marker_count_total": state["reasoning_marker_count"],
        },
        "heuristic_participation_indicators": {
            "participation_level": state["participation_level"],
            "last_response_words": state["last_response_words"],
            "last_english_ratio": state["last_english_ratio"],
        },
        "safety": {
            "input_findings": input_findings,
            "output_findings": output_findings,
            "safe_fallback_substituted": substituted,
        },
        "explainability": {
            "selected_move": move,
            "selected_scaffold": scaffold,
            "decision_reasons": explain_move(move, scaffold, input_findings, state, len(session["turns"]) + 1),
            "generation_engine": generation_engine,
        },
    }
    session["turns"].append(turn)
    save_session(session)
    return session


def explain_move(move: str, scaffold: str, input_findings: list[dict], state: dict, turn_number: int) -> list[str]:
    reasons = []
    if turn_number == 1 and move == "IBI":
        reasons.append("The first turn invites the learner to build on ideas from the video.")
    if input_findings:
        reasons.append("Safeguarding indicators were detected, so the system prioritised motivational safety support.")
    if scaffold == "vocabulary_bridge":
        reasons.append("The student requested comprehension support, so the system used vocabulary bridging.")
    if state.get("reasoning_depth") == "low" and move == "EOR":
        reasons.append("Low reasoning depth triggered elicitation of reasoning.")
    if state.get("participation_level") == "emerging" and move == "MS":
        reasons.append("Brief participation triggered autonomy-supportive motivational scaffolding.")
    if not reasons:
        reasons.append("The move was selected from the current dialogue state and recent move sequence.")
    return reasons


def session_monitoring(session: dict) -> dict:
    state = session.get("dialogue_state", {})
    patterns = []
    if session.get("flags"):
        patterns.append({"severity": "high", "type": "safeguarding_flags", "description": f"{len(session['flags'])} flagged input event(s)."})
    turns = session.get("turns", [])
    if len(turns) >= 3:
        avg_words = sum(turn.get("heuristic_participation_indicators", {}).get("last_response_words", 0) for turn in turns[-3:]) / 3
        if avg_words < 5:
            patterns.append({"severity": "medium", "type": "low_participation", "description": "The last three turns are very short."})
    if len(turns) >= 3 and state.get("reasoning_marker_count", 0) == 0:
        patterns.append({"severity": "medium", "type": "limited_reasoning", "description": "No reasoning markers after three turns."})
    if session.get("status") == "active" and not session.get("chatbot_listening", True):
        patterns.append({"severity": "low", "type": "student_chatbot_stopped", "description": "The student has stopped the chatbot listener."})

    move_counts = {}
    input_modes = {"speech": 0, "typed": 0}
    english_ratios = []
    word_counts = []
    for turn in turns:
        move_counts[turn.get("move", "")] = move_counts.get(turn.get("move", ""), 0) + 1
        mode = turn.get("input_mode", "typed")
        input_modes[mode] = input_modes.get(mode, 0) + 1
        participation = turn.get("heuristic_participation_indicators", {})
        english_ratios.append(float(participation.get("last_english_ratio", 0) or 0))
        word_counts.append(int(participation.get("last_response_words", 0) or 0))

    avg_english_ratio = round(sum(english_ratios) / len(english_ratios), 2) if english_ratios else 0
    avg_words = round(sum(word_counts) / len(word_counts), 1) if word_counts else 0
    return {
        "turn_count": len(turns),
        "participation_level": state.get("participation_level"),
        "reasoning_depth": state.get("reasoning_depth"),
        "reasoning_marker_total": state.get("reasoning_marker_count", 0),
        "average_english_ratio": avg_english_ratio,
        "average_words_per_turn": avg_words,
        "input_modes": input_modes,
        "move_counts": move_counts,
        "move_sequence": state.get("move_sequence", []),
        "patterns": patterns,
        "last_turn_at": turns[-1]["timestamp"] if turns else None,
        "intervention_count": len(session.get("teacher_actions", [])),
        "teacher_note_count": len(session.get("teacher_notes", [])),
        "student_task": session.get("student_task", ""),
        "student_video_upload": session.get("student_video_upload"),
        "teacher_attention_required": any(item["severity"] == "high" for item in patterns),
    }


def student_account_roster() -> list[dict]:
    rows = []
    for account in STUDENT_ACCOUNTS.values():
        row = dict(account)
        session = SESSIONS.get(account.get("active_session_id", ""))
        if session:
            row["monitoring"] = session_monitoring(session)
            row["active_session"] = {
                "id": session["id"],
                "status": session.get("status"),
                "chatbot_listening": bool(session.get("chatbot_listening", False)),
                "material_title": session.get("material_title"),
                "level": session.get("level"),
                "updated_at": session.get("updated_at"),
                "turn_count": len(session.get("turns", [])),
                "flags": len(session.get("flags", [])),
            }
        else:
            row["monitoring"] = None
            row["active_session"] = None
        rows.append(row)
    return sorted(rows, key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)


def teacher_governance_summary(sessions: list[dict]) -> dict:
    monitoring_rows = [session_monitoring(session) for session in sessions]
    active_sessions = sum(1 for session in sessions if session.get("status") == "active")
    listening = sum(1 for session in sessions if session.get("chatbot_listening"))
    total_turns = sum(len(session.get("turns", [])) for session in sessions)
    flags = sum(len(session.get("flags", [])) for session in sessions)
    attention = sum(1 for monitoring in monitoring_rows if monitoring.get("teacher_attention_required"))
    registered = len(STUDENT_ACCOUNTS)
    connected_accounts = sum(1 for account in STUDENT_ACCOUNTS.values() if account.get("active_session_id"))
    return {
        "registered_accounts": registered,
        "max_accounts": MAX_STUDENT_ACCOUNTS,
        "remaining_account_slots": max(0, MAX_STUDENT_ACCOUNTS - registered),
        "connected_accounts": connected_accounts,
        "sessions": len(sessions),
        "active_sessions": active_sessions,
        "chatbot_listening": listening,
        "total_turns": total_turns,
        "flagged_events": flags,
        "teacher_attention_required": attention,
        "governance_scope": "macro_level_multi_turn_session_monitoring",
        "micro_filtering": "system2_single_turn_output_filtering",
        "no_grades_or_profiles": True,
    }


def build_audit(session: dict) -> dict:
    audit = {
        "session_id": session["id"],
        "participant_hash": session.get("participant_hash"),
        "material_id": session.get("material_id"),
        "generated_at": now_iso(),
        "turn_audits": [],
        "summary": session_monitoring(session),
    }
    for turn in session.get("turns", []):
        audit["turn_audits"].append(
            {
                "turn": turn["turn"],
                "move": turn["move"],
                "move_name": turn["move_name"],
                "scaffold": turn["scaffold"],
                "decision_reasons": turn["explainability"]["decision_reasons"],
                "safety": turn["safety"],
                "student_text": redact(turn["student_text"]),
                "ai_response": redact(turn["ai_response"]),
            }
        )
    save_json(AUDITS_DIR / f"{session['id']}-audit.json", audit)
    return audit


def redact(text: str) -> str:
    text = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]", text)
    text = re.sub(r"[\w.\-]+@[\w.\-]+\.\w+", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b\d{15,18}[0-9Xx]?\b", "[REDACTED_ID]", text)
    return text


def anonymised_session_dataset(session: dict) -> dict:
    research_student = RESEARCH_GOVERNANCE.get("students", {}).get(session.get("participant_code", ""), {})
    return {
        "session_hash": hashlib.sha256(ANON_SALT + session["id"].encode("utf-8")).hexdigest()[:18],
        "participant_hash": session.get("participant_hash"),
        "class_id": research_student.get("class_id", ""),
        "condition": research_student.get("condition", ""),
        "teacher_id": research_student.get("teacher_id", ""),
        "material_id": session.get("material_id"),
        "topic": session.get("topic"),
        "level": session.get("level"),
        "lesson_context": session.get("lesson_context") or {},
        "turns": [
            {
                "turn": turn["turn"],
                "timestamp": turn["timestamp"],
                "input_mode": turn["input_mode"],
                "student_text": redact(turn["student_text"]),
                "ai_response": redact(turn["ai_response"]),
                "move": turn["move"],
                "move_name": turn.get("move_name", ""),
                "scaffold": turn["scaffold"],
                "heuristics": {
                    "elaboration": turn["heuristic_elaboration_indicators"],
                    "participation": turn["heuristic_participation_indicators"],
                },
                "safety": turn["safety"],
            }
            for turn in session.get("turns", [])
        ],
        "constraints": {"anonymised": True, "no_voice_recording": True, "no_automated_grading": True},
    }


def ena_ready_rows(sessions: list[dict]) -> list[dict]:
    rows = []
    for session in sessions:
        research_student = RESEARCH_GOVERNANCE.get("students", {}).get(session.get("participant_code", ""), {})
        lesson = session.get("lesson_context") or {}
        for turn in session.get("turns", []):
            rows.append(
                {
                    "participant_hash": session.get("participant_hash"),
                    "session_hash": hashlib.sha256(ANON_SALT + session["id"].encode("utf-8")).hexdigest()[:18],
                    "class_id": research_student.get("class_id", ""),
                    "condition": research_student.get("condition", ""),
                    "teacher_id": research_student.get("teacher_id", ""),
                    "unit": lesson.get("unit", ""),
                    "lesson_cycle": lesson.get("lesson_cycle", ""),
                    "phase": lesson.get("phase", ""),
                    "context": "AI-mediated interaction",
                    "speaker": "student_ai_turn",
                    "turn": turn.get("turn"),
                    "timestamp": turn.get("timestamp"),
                    "tech_seda_feature": turn.get("move"),
                    "tech_seda_feature_name": turn.get("move_name"),
                    "scaffold": turn.get("scaffold"),
                    "window_id": f"{session['id']}-{max(1, int((turn.get('turn', 1) - 1) / 3) + 1)}",
                }
            )
    return rows


def export_dataset(session: dict) -> dict:
    data = {"exported_at": now_iso(), **anonymised_session_dataset(session), "ena_rows": ena_ready_rows([session])}
    path = EXPORTS_DIR / f"{session['id']}-anonymised-dataset.json"
    save_json(path, data)
    return {"file": path.name, "url": rel_media(path), "dataset": data}


def export_all_datasets() -> dict:
    sessions = sorted(SESSIONS.values(), key=lambda item: item.get("created_at", ""))
    exported_at = now_iso()
    data = {
        "exported_at": exported_at,
        "platform": "Integrated Local AI-Supported English Learning Platform",
        "governance_layer": "System 3 teacher governance and research data stewardship",
        "summary": teacher_governance_summary(sessions),
        "accounts": [
            {
                "participant_hash": account.get("participant_hash"),
                "level": account.get("level"),
                "created_at": account.get("created_at"),
                "session_count": len(account.get("session_ids", [])),
            }
            for account in student_account_roster()
        ],
        "sessions": [anonymised_session_dataset(session) for session in sessions],
        "ena_rows": ena_ready_rows(sessions),
        "assessment_records": anonymise_research_records(RESEARCH_GOVERNANCE.get("assessment_records", [])),
        "human_coding": anonymise_research_records(RESEARCH_GOVERNANCE.get("human_coding", [])),
        "imi_surveys": anonymise_research_records(RESEARCH_GOVERNANCE.get("imi_surveys", [])),
        "teacher_reflections": RESEARCH_GOVERNANCE.get("teacher_reflections", []),
        "fidelity_logs": RESEARCH_GOVERNANCE.get("fidelity_logs", []),
        "comparison_logs": RESEARCH_GOVERNANCE.get("comparison_logs", []),
        "safeguarding_cases": RESEARCH_GOVERNANCE.get("safeguarding_cases", []),
        "dataset_approvals": RESEARCH_GOVERNANCE.get("dataset_approvals", []),
        "constraints": {
            "anonymised": True,
            "no_student_names": True,
            "no_voice_recordings": True,
            "no_photos_or_biometrics": True,
            "no_automated_grading": True,
            "post_session_research_review_only": True,
        },
    }
    path = EXPORTS_DIR / f"all-sessions-anonymised-dataset-{int(time.time())}.json"
    save_json(path, data)
    return {"file": path.name, "url": rel_media(path), "dataset": data}


def anonymise_research_records(records: list[dict]) -> list[dict]:
    output = []
    for record in records:
        item = dict(record)
        code = item.pop("participant_code", "")
        if code and not item.get("participant_hash"):
            item["participant_hash"] = participant_hash(sanitize_code(code))
        output.append(item)
    return output


def export_ena_csv() -> dict:
    rows = ena_ready_rows(sorted(SESSIONS.values(), key=lambda item: item.get("created_at", "")))
    path = EXPORTS_DIR / f"ena-ready-dialogic-features-{int(time.time())}.csv"
    fieldnames = [
        "participant_hash",
        "session_hash",
        "class_id",
        "condition",
        "teacher_id",
        "unit",
        "lesson_cycle",
        "phase",
        "context",
        "speaker",
        "turn",
        "timestamp",
        "tech_seda_feature",
        "tech_seda_feature_name",
        "scaffold",
        "window_id",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return {"file": path.name, "url": rel_media(path), "row_count": len(rows)}


def research_summary() -> dict:
    return {
        "classes": len(RESEARCH_GOVERNANCE.get("classes", {})),
        "research_students": len(RESEARCH_GOVERNANCE.get("students", {})),
        "assessment_records": len(RESEARCH_GOVERNANCE.get("assessment_records", [])),
        "fidelity_logs": len(RESEARCH_GOVERNANCE.get("fidelity_logs", [])),
        "comparison_logs": len(RESEARCH_GOVERNANCE.get("comparison_logs", [])),
        "human_coding": len(RESEARCH_GOVERNANCE.get("human_coding", [])),
        "imi_surveys": len(RESEARCH_GOVERNANCE.get("imi_surveys", [])),
        "teacher_reflections": len(RESEARCH_GOVERNANCE.get("teacher_reflections", [])),
        "safeguarding_cases": len(RESEARCH_GOVERNANCE.get("safeguarding_cases", [])),
        "dataset_approvals": len(RESEARCH_GOVERNANCE.get("dataset_approvals", [])),
        "current_lesson": current_lesson_context(),
    }


def teacher_action(session: dict, action: str, role: str) -> dict:
    if action == "pause":
        session["status"] = "paused"
    elif action == "resume":
        session["status"] = "active"
    elif action == "terminate":
        session["status"] = "terminated"
        session["chatbot_listening"] = False
        session["dialogue_state"]["volatile_memory_purged_at"] = now_iso()
    elif action == "flag_review":
        session.setdefault("flags", []).append(
            {
                "time": now_iso(),
                "turn": len(session.get("turns", [])),
                "type": "teacher_marked_for_researcher_review",
                "findings": [{"category": "teacher_review", "matches": ["manual_flag"]}],
            }
        )
    else:
        raise ValueError("Unknown action.")
    event = {"time": now_iso(), "role": role, "action": action}
    session["teacher_actions"].append(event)
    save_session(session)
    log_action(role, f"session_{action}", {"session_id": session["id"]})
    return session


class IntegratedHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{now_iso()}] {self.address_string()} {fmt % args}")

    def role(self, allowed: set[str] | None = None) -> str | None:
        header = self.headers.get("Authorization", "")
        role = verify_token(header.removeprefix("Bearer ").strip())
        if not role or (allowed and role not in allowed):
            self.send_json({"error": "Unauthorized"}, status=401)
            return None
        return role

    def send_json(self, data, status: int = 200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path, *, head_only: bool = False):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".vtt":
            content_type = "text/vtt"
        file_size = path.stat().st_size
        range_header = self.headers.get("Range")

        if range_header and range_header.startswith("bytes="):
            range_spec = range_header.removeprefix("bytes=").split(",", 1)[0]
            start_text, _, end_text = range_spec.partition("-")
            try:
                if start_text:
                    start = int(start_text)
                    end = int(end_text) if end_text else file_size - 1
                else:
                    suffix = int(end_text)
                    start = max(0, file_size - suffix)
                    end = file_size - 1
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
            except ValueError:
                self.send_error(416)
                return
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            if not head_only:
                with path.open("rb") as file:
                    file.seek(start)
                    self.wfile.write(file.read(length))
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        if not head_only:
            with path.open("rb") as file:
                shutil.copyfileobj(file, self.wfile)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/student"}:
                self.send_file(STATIC_DIR / "student.html")
            elif path == "/teacher":
                self.send_file(STATIC_DIR / "teacher.html")
            elif path.startswith("/static/"):
                target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
                try:
                    target.relative_to(STATIC_DIR.resolve())
                except ValueError:
                    self.send_error(403)
                    return
                self.send_file(target)
            elif path.startswith("/media/"):
                target = safe_runtime_path(path.removeprefix("/media/"))
                if not target:
                    self.send_error(403)
                    return
                self.send_file(target)
            elif path == "/api/config":
                self.send_json(
                    {
                        "platform_name": "A Locally Hosted AI-Supported Multimodal English Learning and Research Governance Platform",
                        "cn_name": "本地化 AI 支持的多模态英语学习与研究治理一体化平台",
                        "ports": {"current": PORT},
                        "features": ["student_video_chat", "teacher_monitoring", "content_adaptation", "explainability", "dataset_export"],
                        "demo_login": {"teacher": "teacher-demo", "researcher": "researcher-demo"},
                        "student_account_capacity": MAX_STUDENT_ACCOUNTS,
                    }
                )
            elif path == "/api/materials/current":
                self.send_json({"material": ensure_demo_material()})
            elif path == "/api/materials":
                self.send_json({"materials": sorted(MATERIALS.values(), key=lambda item: item["created_at"], reverse=True)})
            elif path == "/api/teacher/state":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                sessions = sorted(SESSIONS.values(), key=lambda item: item["updated_at"], reverse=True)
                self.send_json(
                    {
                        "materials": sorted(MATERIALS.values(), key=lambda item: item["created_at"], reverse=True),
                        "sessions": [{"session": session, "monitoring": session_monitoring(session)} for session in sessions],
                        "accounts": student_account_roster(),
                        "summary": teacher_governance_summary(sessions),
                        "actions": load_json(ACTIONS_FILE, []),
                    }
                )
            elif path == "/api/research/state":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"research": RESEARCH_GOVERNANCE, "summary": research_summary()})
            elif path.startswith("/api/sessions/") and path.endswith("/record"):
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                self.send_json({"session": session, "monitoring": session_monitoring(session), "audit": build_audit(session)})
            elif path.startswith("/api/sessions/") and path.endswith("/audit"):
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                self.send_json({"audit": build_audit(session)})
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/student"}:
            self.send_file(STATIC_DIR / "student.html", head_only=True)
        elif path == "/teacher":
            self.send_file(STATIC_DIR / "teacher.html", head_only=True)
        elif path.startswith("/static/"):
            target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
            try:
                target.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(403)
                return
            self.send_file(target, head_only=True)
        elif path.startswith("/media/"):
            target = safe_runtime_path(path.removeprefix("/media/"))
            if not target:
                self.send_error(403)
                return
            self.send_file(target, head_only=True)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/login":
                payload = read_json(self)
                role = payload.get("role")
                passcode = payload.get("passcode")
                if (role == "teacher" and passcode == "teacher-demo") or (role == "researcher" and passcode == "researcher-demo"):
                    token = make_token(role)
                    log_action(role, "login")
                    self.send_json({"token": token, "role": role})
                else:
                    self.send_json({"error": "Invalid role or passcode."}, status=401)
            elif path == "/api/materials/topic":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                material = generate_material_from_topic(read_json(self), role)
                self.send_json({"material": material})
            elif path == "/api/research/class":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"class_group": upsert_class_group(read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/student":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"student": upsert_research_student(read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/lesson":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"lesson": set_lesson_context(read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/assessments/import":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json(import_assessment_records(read_json(self), role))
            elif path == "/api/research/fidelity":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"record": append_research_record("fidelity_logs", read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/comparison-log":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"record": append_research_record("comparison_logs", read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/human-coding":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"record": append_research_record("human_coding", read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/imi-survey":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"record": append_research_record("imi_surveys", read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/reflection":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"record": append_research_record("teacher_reflections", read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/safeguarding-case":
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                self.send_json({"case": upsert_safeguarding_case(read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/dataset-approval":
                role = self.role({"researcher"})
                if not role:
                    return
                self.send_json({"approval": save_dataset_approval(read_json(self), role), "summary": research_summary()})
            elif path == "/api/research/export-ena":
                role = self.role({"researcher"})
                if not role:
                    return
                exported = export_ena_csv()
                log_action(role, "ena_ready_dataset_exported", {"file": exported["file"], "rows": exported["row_count"]})
                self.send_json(exported)
            elif path == "/api/student/system1/topic":
                material = generate_system1_topic_material(read_json(self))
                self.send_json({"material": material})
            elif path == "/api/student/system1/video":
                material = receive_system1_video_material(self)
                self.send_json({"material": material})
            elif path == "/api/student/video-upload":
                upload = receive_student_video_upload(self)
                log_action("student", "student_video_uploaded", {"upload_id": upload["id"], "file": upload["original_filename"]})
                self.send_json({"upload": upload})
            elif path == "/api/tts":
                self.send_json(make_tts_audio(read_json(self)))
            elif path == "/api/student/register":
                payload = read_json(self)
                account = register_student_account({**payload, "source": "student_registration"})
                log_action("student", "student_account_registered", {"participant_hash": account["participant_hash"]})
                self.send_json({"account": account, "max_accounts": MAX_STUDENT_ACCOUNTS})
            elif path == "/api/student/sessions":
                session = create_session(read_json(self))
                self.send_json({"session": session})
            elif path.startswith("/api/sessions/") and path.endswith("/turns"):
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                self.send_json({"session": add_turn(session, read_json(self))})
            elif path.startswith("/api/sessions/") and path.endswith("/student-control"):
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                payload = read_json(self)
                session["chatbot_listening"] = bool(payload.get("chatbot_listening"))
                save_session(session)
                self.send_json({"session": session})
            elif path.startswith("/api/sessions/") and path.endswith("/teacher-action"):
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                payload = read_json(self)
                self.send_json({"session": teacher_action(session, payload.get("action", ""), role)})
            elif path.startswith("/api/sessions/") and path.endswith("/teacher-note"):
                role = self.role({"teacher", "researcher"})
                if not role:
                    return
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                payload = read_json(self)
                note = re.sub(r"\s+", " ", (payload.get("note") or "").strip())[:1600]
                if not note:
                    raise ValueError("Teacher note is empty.")
                entry = {"time": now_iso(), "role": role, "note": note}
                session.setdefault("teacher_notes", []).append(entry)
                save_session(session)
                log_action(role, "teacher_note_saved", {"session_id": session_id})
                self.send_json({"session": session, "note": entry})
            elif path.startswith("/api/sessions/") and path.endswith("/export"):
                role = self.role({"researcher"})
                if not role:
                    return
                session_id = path.split("/")[3]
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error(404)
                    return
                exported = export_dataset(session)
                log_action(role, "dataset_exported", {"session_id": session_id, "file": exported["file"]})
                self.send_json(exported)
            elif path == "/api/teacher/export-all":
                role = self.role({"researcher"})
                if not role:
                    return
                exported = export_all_datasets()
                log_action(role, "all_datasets_exported", {"file": exported["file"]})
                self.send_json(exported)
            else:
                self.send_error(404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)


def main():
    load_state()
    ensure_demo_material()
    server = ThreadingHTTPServer((HOST, PORT), IntegratedHandler)
    print(f"Integrated local AI learning platform running at http://{HOST}:{PORT}")
    print("Student page: /student")
    print("Teacher page: /teacher")
    server.serve_forever()


if __name__ == "__main__":
    main()
