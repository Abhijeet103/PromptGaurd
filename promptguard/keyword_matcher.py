# ================================================================
from flashtext import KeywordProcessor

from .data import rules

RULES = rules


try:
    from rapidfuzz import fuzz
    FAST_FUZZY_AVAILABLE = True
except Exception:
    FAST_FUZZY_AVAILABLE = False


class KeywordMatcher:
    """Ultra-fast keyword matcher using FlashText."""
    def __init__(self):
        self.processor = KeywordProcessor(case_sensitive=False)
        for category, patterns in RULES.items():
            for p in patterns:
                self.processor.add_keyword(p, category)

    def search(self, text: str):
        found = self.processor.extract_keywords(text)
        matches = []
        for keyword in found:
            cat = self.processor.get_keyword(keyword)
            matches.append({"category": cat, "pattern": keyword})
        return matches

    def fuzzy_search(self, text: str, threshold=85):
        if not FAST_FUZZY_AVAILABLE:
            return []
        matches = []
        t = text.lower()
        for cat, patterns in RULES.items():
            for p in patterns:
                score = fuzz.partial_ratio(p.lower(), t)
                if score >= threshold:
                    matches.append({"category": cat, "pattern": p, "score": score})
        return matches
