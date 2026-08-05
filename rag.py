"""Retrieval over the knowledge base.

BM25 over markdown sections, implemented in the standard library on purpose:
the baseline needs zero dependencies and zero API keys so anyone can run it,
and for a help-center-sized corpus (dozens to hundreds of articles) lexical
search is a strong baseline. The upgrade path to embeddings is described in
the README; the interface below does not change when you swap the scorer.
"""

import math
import os
import re
from collections import Counter

KB_DIR = os.environ.get("HELPBOT_KB_DIR", os.path.join(os.path.dirname(__file__), "kb"))

_WORD = re.compile(r"[a-z0-9']+")

# Small stopword list; enough to keep scores meaningful on short IT questions.
_STOP = set(
    "a an and are as at be but by for from has have how i if in is it my of on or "
    "our so that the their this to was we what when where which who will with you your".split()
)


def _stem(token):
    """Crude suffix stripping, applied to both queries and documents.

    Not linguistics, just a matching normalizer: "printers", "printer", and
    "printing" should all land on the same term. Kept deliberately simple;
    the eval set is what says whether it is good enough.
    """
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
    if len(token) > 4 and token.endswith(("ors", "ers")):
        token = token[:-1]
    if len(token) > 4 and token.endswith(("or", "er")):
        token = token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _tokens(text):
    text = text.lower().replace("wi-fi", "wifi")
    return [_stem(t) for t in _WORD.findall(text) if t not in _STOP]


def load_chunks(kb_dir=None):
    """Split every kb/*.md article into sections keyed by heading.

    Each chunk carries the article path and heading so answers can cite
    exactly where they came from.
    """
    kb_dir = kb_dir or KB_DIR
    chunks = []
    for name in sorted(os.listdir(kb_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(kb_dir, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        title = name
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            title = m.group(1).strip()
        # Split on ## headings; the preamble before the first ## is its own chunk.
        parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
        preamble = parts[0].strip()
        if preamble:
            chunks.append({"article": "kb/" + name, "title": title, "heading": title, "text": preamble})
        for part in parts[1:]:
            lines = part.strip().splitlines()
            heading = lines[0].strip() if lines else ""
            body = "\n".join(lines[1:]).strip()
            if body:
                chunks.append({"article": "kb/" + name, "title": title, "heading": heading, "text": body})
    return chunks


class Retriever:
    """BM25 with a title/heading boost."""

    K1 = 1.5
    B = 0.75
    TITLE_BOOST = 0.5  # a query term matching the article title or heading counts extra

    def __init__(self, chunks=None):
        self.chunks = chunks if chunks is not None else load_chunks()
        self._doc_tokens = [_tokens(c["text"]) for c in self.chunks]
        self._head_tokens = [set(_tokens(c["title"] + " " + c["heading"])) for c in self.chunks]
        self._doc_len = [len(t) for t in self._doc_tokens]
        self._avg_len = (sum(self._doc_len) / len(self._doc_len)) if self.chunks else 0.0
        self._df = Counter()
        for toks in self._doc_tokens:
            for term in set(toks):
                self._df[term] += 1
        self._n = len(self.chunks)

    def _idf(self, term):
        df = self._df.get(term, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query, k=3):
        """Return the top-k chunks as (score, chunk) pairs, best first."""
        q = _tokens(query)
        scored = []
        for i, chunk in enumerate(self.chunks):
            tf = Counter(self._doc_tokens[i])
            score = 0.0
            for term in q:
                if term not in tf and term not in self._head_tokens[i]:
                    continue
                idf = self._idf(term)
                f = tf.get(term, 0)
                denom = f + self.K1 * (1 - self.B + self.B * self._doc_len[i] / (self._avg_len or 1))
                score += idf * (f * (self.K1 + 1) / denom if denom else 0.0)
                if term in self._head_tokens[i]:
                    score += idf * self.TITLE_BOOST
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:k]
