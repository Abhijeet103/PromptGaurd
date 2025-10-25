import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from flashtext import KeywordProcessor

from .data import rules
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
        """Optional fuzzy match for typos or variants."""
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

class PromptGuard:
    """
    Multilingual, layered prompt injection detection:
      1️⃣ Keyword + regex heuristics
      2️⃣ Sensitive action detection
      3️⃣ Multilingual semantic similarity (MiniLM)
      4️⃣ Fuzzy fallback
    """
    def __init__(self, semantic=True, threshold=0.78, multilingual=True, fuzzy=False, translate_fallback=True):
        self.keyword_matcher = KeywordMatcher()
        self.semantic = semantic
        self.threshold = threshold
        self.multilingual = multilingual
        self.fuzzy = fuzzy
        self.translate_fallback = translate_fallback

        if semantic:
            model_name = "paraphrase-multilingual-MiniLM-L12-v2" if multilingual else "all-MiniLM-L6-v2"
            self.model = SentenceTransformer(model_name)
            self._prepare_pattern_vectors()

    def _prepare_pattern_vectors(self):
        """Pre-encode all known bad patterns."""
        self.patterns = []
        self.pattern_cats = []
        for cat, pats in RULES.items():
            for p in pats:
                self.patterns.append(p)
                self.pattern_cats.append(cat)
        self.pattern_vecs = self.model.encode(self.patterns, normalize_embeddings=True, show_progress_bar=False)

    def analyze(self, text: str) -> dict:
        if not text or not text.strip():
            return {"safe": True, "matches": []}

        # Keep both normalized and raw text
        text_raw = text.strip()
        text_norm = normalize_text(text_raw)
        sentences = smart_split_sentences(text_norm)
        matches = []

        # 1️⃣ Keyword heuristic
        kw_hits = self.keyword_matcher.search(text_norm)
        if kw_hits:
            return {"safe": False, "risk": "HIGH", "reason": "keyword_match", "matches": kw_hits}

        # 2️⃣ Sensitive-action detector
        for s in sentences:
            if contains_sensitive_action(s):
                matches.append({"category": "heuristic", "sentence": s, "reason": "sensitive_action"})
                return {"safe": False, "risk": "HIGH", "matches": matches}

        # 3️⃣ Multilingual Semantic Similarity
        if self.semantic:
            multilingual_sentences = smart_split_sentences(text_raw)
            # Optional translation fallback for non-English
            if self.translate_fallback:
                multilingual_sentences = [translate_to_english(s) for s in multilingual_sentences]

            sent_vecs = self.model.encode(multilingual_sentences, normalize_embeddings=True, show_progress_bar=False)
            sims = cosine_similarity(sent_vecs, self.pattern_vecs)
            max_sim = float(np.max(sims))

            if max_sim > self.threshold:
                i, j = np.unravel_index(np.argmax(sims), sims.shape)
                cat = self.pattern_cats[j]
                sentence = multilingual_sentences[i]
                matches.append({"category": cat, "sentence": sentence, "similarity": round(max_sim, 3)})
                risk = "HIGH" if max_sim > 0.9 else "MEDIUM"
                return {"safe": False, "risk": risk, "reason": "semantic_match", "matches": matches}

        # 4️⃣ Fuzzy fallback
        if self.fuzzy:
            fuzzy_hits = self.keyword_matcher.fuzzy_search(text_norm)
            if fuzzy_hits:
                return {"safe": False, "risk": "HIGH", "reason": "fuzzy_match", "matches": fuzzy_hits}

        return {"safe": True, "matches": []}
