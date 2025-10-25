import re
import string

LEET_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"
})

ACTION_WORDS = {"upload", "send", "push", "share", "leak", "commit", "expose"}
SENSITIVE_WORDS = {"api key", "token", "password", "credential", "secret", "env var"}

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower().translate(LEET_MAP)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[`\"']", " ", s)
    s = re.sub(rf"[{re.escape(string.punctuation)}]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def split_lines(text: str):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]

def contains_sensitive_action(text: str) -> bool:
    """Fast lexical heuristic: both sensitive term + action verb"""
    t = text.lower()
    return any(a in t for a in ACTION_WORDS) and any(s in t for s in SENSITIVE_WORDS)
