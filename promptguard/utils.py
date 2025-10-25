import re
import string
from typing import List

try:
    from langdetect import detect
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except Exception:
    TRANSLATION_AVAILABLE = False

LEET_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "8": "b", "|": "l", "!": "i"
})

ACTION_WORDS = {
    "upload", "send", "push", "share", "leak", "commit", "expose",
    "dump", "export", "copy", "transfer", "download", "exfiltrate",
    "delete", "drop", "remove", "wipe", "destroy", "truncate", "rm", "shutdown"
}
SENSITIVE_WORDS = {
    "api key", "token", "password", "credential", "secret", "env var",
    "secrets", "database", "db", "table", "credentials", "private key", "key"
}

BASE64_RE = re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")
URL_RE = re.compile(r"(https?://[^\s]+|s3://[^\s]+)", re.I)

# ==========================================================
# ✨ Improved Multilingual Handling
# ==========================================================
def detect_language(text: str) -> str:
    """Detects text language safely."""
    if not text.strip():
        return "en"
    try:
        return detect(text)
    except Exception:
        return "en"

def translate_to_english(text: str) -> str:
    """Translates non-English text to English (fallback)."""
    if not TRANSLATION_AVAILABLE:
        return text
    try:
        lang = detect_language(text)
        if lang != "en":
            return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        pass
    return text

# ==========================================================
# Normalization & Sentence Handling
# ==========================================================
def normalize_text(s: str) -> str:
    """
    Lowercase, map leet, remove punctuation for English-like text.
    Non-ASCII characters are preserved for multilingual embeddings.
    """
    if not s:
        return ""
    s = s.lower().translate(LEET_MAP)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"s3://\S+", " s3://bucket ", s)
    s = re.sub(r"[`\"']", " ", s)
    s = re.sub(r"([{}])".format(re.escape(string.punctuation)), " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def smart_split_sentences(text: str) -> List[str]:
    """Splits text into sentences safely across multiple scripts."""
    if not text:
        return []
    text = re.sub(r'([.!?])(?=[A-Za-z0-9"\'\[])', r'\1 ', text)
    parts = re.split(r'[.!?]+|\n|;|\|\||&&', text)
    return [p.strip() for p in parts if p and p.strip()]

def looks_like_base64(text: str) -> bool:
    return bool(BASE64_RE.search(text))

def contains_url(text: str) -> bool:
    return bool(URL_RE.search(text))

# ==========================================================
# Heuristic Sensitive-Action Detector
# ==========================================================
_DESTRUCTIVE_VERBS = r"(delete|drop|remove|destroy|wipe|erase|rm|truncate|shutdown|kill)"
_EXFIL_VERBS = r"(upload|send|exfiltrate|export|copy|transfer|push|scp|ftp|aws|gcs|curl)"
_TARGETS = r"(database|db|table|dump|backup|credentials|secrets|api ?key|token|password|key|env|environment|file)"

_DESTRUCTIVE_PATTERN = re.compile(rf"\b({_DESTRUCTIVE_VERBS})\b.*\b({_TARGETS})\b", re.I)
_EXFIL_PATTERN = re.compile(rf"\b({_EXFIL_VERBS})\b.*\b({_TARGETS}|s3://)\b", re.I)

def contains_sensitive_action(text: str) -> bool:
    """Catches imperative commands or dangerous data references."""
    if not text:
        return False
    t = " ".join(text.split())
    if _DESTRUCTIVE_PATTERN.search(t) or _EXFIL_PATTERN.search(t):
        return True
    if contains_url(t) and re.search(r"(upload|send|exfiltrate|export|copy|transfer|database|secret|backup)", t, re.I):
        return True
    if looks_like_base64(t):
        return True
    if any(a in t for a in ACTION_WORDS) and any(s in t for s in SENSITIVE_WORDS):
        return True
    return False
