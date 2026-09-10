"""Local BM25 retrieval with normalized bilingual terms and alias boosts."""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from knowledge.bank import ID_INDEX, KEYWORD_MAP, KNOWLEDGE_ENTRIES


def _tokenize(text: str) -> List[str]:
    """Tokenize Chinese and English text into word and character n-grams."""
    if not text:
        return []
    from knowledge.bank import normalize_term
    s = normalize_term(text)
    # Extract English tokens
    en_words = re.findall(r"[a-z0-9_\-\+]+", s)
    # Extract Chinese chars
    zh_chars = re.findall(r"[\u4e00-\u9fa5]", s)
    # 2-grams for Chinese
    zh_2grams = []
    if len(zh_chars) >= 2:
        for i in range(len(zh_chars) - 1):
            zh_2grams.append(zh_chars[i] + zh_chars[i + 1])

    return en_words + zh_chars + zh_2grams


class KnowledgeRAGRetriever:
    """Hybrid BM25 + Keyword RAG engine for knowledge retrieval."""

    def __init__(self, entries: List[Dict[str, Any]]):
        self.entries = entries
        self.corpus_docs: List[Dict[str, Any]] = []
        self.doc_tokens: List[Dict[str, int]] = []
        self.doc_lens: List[int] = []
        self.df: Dict[str, int] = {}
        self.avgdl: float = 1.0
        self.N: int = len(entries)
        self._build_index()

    def _build_index(self):
        self.corpus_docs = []
        self.doc_tokens = []
        self.doc_lens = []
        self.df = {}

        total_len = 0
        for entry in self.entries:
            # Build search document containing all semantic aspects
            q_texts = []
            for q in entry.get("interview_questions", []):
                q_texts.append(q.get("question", "") + " " + q.get("answer", ""))

            doc_text = " ".join([
                entry.get("name", ""),
                " ".join(entry.get("aliases", [])),
                entry.get("category", ""),
                entry.get("definition", ""),
                entry.get("detailed_explanation", ""),
                " ".join(q_texts)
            ])

            tokens = _tokenize(doc_text)
            self.corpus_docs.append(entry)
            self.doc_tokens.append(Counter(tokens))
            l = len(tokens)
            self.doc_lens.append(l)
            total_len += l

            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.df[t] = self.df.get(t, 0) + 1

        self.N = max(1, len(self.corpus_docs))
        self.avgdl = (total_len / self.N) if self.N else 1.0

    def search(self, query: str, top_k: int = 4, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Retrieve the most relevant knowledge entries and interview questions via RAG."""
        if not query or not query.strip():
            return []

        from knowledge.bank import normalize_term, match_knowledge_ids, find_knowledge_by_term
        q_clean = normalize_term(query)
        exact_entry = find_knowledge_by_term(query) if q_clean in KEYWORD_MAP else None
        matched_ids = set(match_knowledge_ids(query))

        q_tokens = _tokenize(query)
        if not q_tokens and not exact_entry:
            return []

        k1 = 1.5
        b = 0.75
        scores: List[Tuple[float, Dict[str, Any]]] = []

        for idx, entry in enumerate(self.corpus_docs):
            d_tokens = self.doc_tokens[idx]
            d_len = self.doc_lens[idx]
            bm25_score = 0.0

            tf_map = d_tokens

            for qt in q_tokens:
                if qt in tf_map:
                    tf = tf_map[qt]
                    doc_freq = self.df.get(qt, 1)
                    # Standard BM25 IDF
                    idf = math.log((self.N - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                    if idf < 0:
                        idf = 0.01
                    term_score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (d_len / self.avgdl)))
                    bm25_score += term_score

            if entry['id'] in matched_ids:
                bm25_score += 15.0
            if exact_entry and entry['id'] == exact_entry['id']:
                bm25_score += 100.0

            if bm25_score > threshold or (exact_entry and entry.get("id") == exact_entry.get("id")):
                scores.append((bm25_score, entry))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, entry in scores[:top_k]:
            item = dict(entry)
            item["relevance_score"] = round(score, 2)
            results.append(item)

        return results


RAG_ENGINE = KnowledgeRAGRetriever(KNOWLEDGE_ENTRIES)


def retrieve_knowledge(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Public helper to retrieve knowledge items and interview QA for any query."""
    return RAG_ENGINE.search(query, top_k=top_k)
