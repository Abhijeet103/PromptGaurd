import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from flashtext import KeywordProcessor

from .data import rules
from .utils import normalize_text, split_lines, contains_sensitive_action

RULES = rules


class KeywordMatcher:
    """Ultra-fast keyword matcher using FlashText (pure Python)."""
    def __init__(self):
        self.processor = KeywordProcessor(case_sensitive=False)
        for category, patterns in RULES.items():
            for p in patterns:
                self.processor.add_keyword(p, category)

    def search(self, text: str):
        """Returns a list of matches with category + pattern."""
        found = self.processor.extract_keywords(text)
        matches = []
        for keyword in found:
            cat = self.processor.get_keyword(keyword)
            matches.append({"category": cat, "pattern": keyword})
        return matches




class PromptGuard:
    """
    Fast, layered prompt injection detection engine.
    - Tier 1: lexical heuristic (keyword + sensitive-action)
    - Tier 2: semantic fallback via MiniLM embeddings
    """

    def __init__(self, semantic=True, threshold=0.85):
        self.keyword_matcher = KeywordMatcher()
        self.semantic = semantic
        self.threshold = threshold
        if semantic:
            # Preload lightweight MiniLM model for semantic similarity
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self._prepare_pattern_vectors()

    def _prepare_pattern_vectors(self):
        """Pre-encode known malicious patterns for semantic similarity checks."""
        self.patterns = []
        self.pattern_cats = []
        for cat, pats in RULES.items():
            for p in pats:
                self.patterns.append(p)
                self.pattern_cats.append(cat)
        self.pattern_vecs = self.model.encode(
            self.patterns, normalize_embeddings=True, show_progress_bar=False
        )


    def analyze(self, text: str) -> dict:
        if not text or not text.strip():
            return {"safe": True, "matches": []}

        text_norm = normalize_text(text)
        lines = split_lines(text_norm)
        matches = []

        kw_hits = self.keyword_matcher.search(text_norm)
        if kw_hits:
            return {"safe": False, "risk": "HIGH", "reason": "keyword_match", "matches": kw_hits}

        for ln in lines:
            if contains_sensitive_action(ln):
                matches.append({
                    "category": "data_exfiltration",
                    "sentence": ln,
                    "reason": "Sensitive action + sensitive term"
                })
                return {"safe": False, "risk": "HIGH", "matches": matches}

        if self.semantic:
            sent_vecs = self.model.encode(lines, normalize_embeddings=True, show_progress_bar=False)
            sims = cosine_similarity(sent_vecs, self.pattern_vecs)
            max_sim = float(np.max(sims))
            if max_sim > self.threshold:
                idx = np.unravel_index(np.argmax(sims), sims.shape)
                cat = self.pattern_cats[idx[1]]
                sentence = lines[idx[0]]
                matches.append({
                    "category": cat,
                    "sentence": sentence,
                    "similarity": round(max_sim, 3)
                })
                risk = "HIGH" if max_sim > 0.9 else "MEDIUM"
                return {"safe": False, "risk": risk, "matches": matches}

        return {"safe": True, "matches": []}
