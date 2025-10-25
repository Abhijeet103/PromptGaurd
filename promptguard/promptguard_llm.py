import re
import numpy as np
from flashtext import KeywordProcessor
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

from .data import rules
from .keyword_matcher import KeywordMatcher
from .llm_intent_classifier import LLMIntentClassifier
from .utils import (
    normalize_text,
    smart_split_sentences,
    contains_sensitive_action,
    translate_to_english,
)

try:
    from rapidfuzz import fuzz
    FAST_FUZZY_AVAILABLE = True
except Exception:
    FAST_FUZZY_AVAILABLE = False


RULES = rules

class PromptGuard:
    """
    Optimized LLM-enhanced prompt injection detector:
      1️⃣ Keyword / regex heuristics
      2️⃣ Sensitive-action detection
      3️⃣ Quantized LLM-based intent classification (multilingual)
      4️⃣ Optional fuzzy fallback
    """
    def __init__(self, llm_model="Qwen/Qwen2.5-0.5B-Instruct", fuzzy=False):
        self.keyword_matcher = KeywordMatcher()
        self.intent_model = LLMIntentClassifier(model_name=llm_model)
        self.fuzzy = fuzzy

    def analyze(self, text: str) -> dict:
        if not text or not text.strip():
            return {"safe": True, "matches": []}

        text_raw = text.strip()
        text_norm = normalize_text(text_raw)
        sentences = smart_split_sentences(text_norm)
        matches = []


        kw_hits = self.keyword_matcher.search(text_norm)
        if kw_hits:
            return {"safe": False, "risk": "HIGH", "reason": "keyword_match", "matches": kw_hits}


        for s in sentences:
            if contains_sensitive_action(s):
                matches.append({
                    "category": "heuristic",
                    "sentence": s,
                    "reason": "Sensitive action detected"
                })
                return {"safe": False, "risk": "HIGH", "matches": matches}


        malicious_found = False
        for s in sentences:
            label = self.intent_model.classify(s)
            if label == "MALICIOUS":
                malicious_found = True
                matches.append({
                    "category": "semantic_llm",
                    "sentence": s,
                    "reason": "LLM intent classification = MALICIOUS"
                })

        if malicious_found:
            return {"safe": False, "risk": "HIGH", "reason": "llm_intent", "matches": matches}


        if self.fuzzy:
            fuzzy_hits = self.keyword_matcher.fuzzy_search(text_norm)
            if fuzzy_hits:
                return {"safe": False, "risk": "MEDIUM", "reason": "fuzzy_match", "matches": fuzzy_hits}

        return {"safe": True, "matches": []}
