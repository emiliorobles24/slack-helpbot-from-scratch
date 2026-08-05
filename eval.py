"""Eval harness: does retrieval find the right article, and does the gate refuse
what it should refuse?

Runs in CI on every push (standard library only, no API key). Two checks:

1. Coverage: for each golden question, is the expected article in the top-3
   retrieved chunks? Target: at least 80% hit rate.
2. Refusal: out-of-scope questions must score below the grounding gate, so
   the bot escalates instead of improvising. Target: all of them.

Phrasings deliberately avoid quoting the articles verbatim; employees do not
talk like documentation.
"""

import sys

from answer import MIN_SCORE
from rag import Retriever

GOLDEN = [
    ("i forgot my okta password and cant log in", "kb/password-reset.md"),
    ("locked out of my account after too many attempts", "kb/password-reset.md"),
    ("how do i get on the vpn from home", "kb/vpn-access.md"),
    ("vpn keeps disconnecting every few minutes", "kb/vpn-access.md"),
    ("got a new phone and my mfa codes are gone", "kb/mfa-reset.md"),
    ("lost my phone, worried someone can approve my push notifications", "kb/mfa-reset.md"),
    ("printer on 4 wont print my document", "kb/printers.md"),
    ("how do i add the office printer to my mac", "kb/printers.md"),
    ("my laptop battery dies in an hour, can i get a replacement", "kb/laptop-requests.md"),
    ("new hire starting monday needs a laptop", "kb/laptop-requests.md"),
    ("customer visiting tomorrow needs wifi", "kb/guest-wifi.md"),
    ("what is the guest network password", "kb/guest-wifi.md"),
]

OUT_OF_SCOPE = [
    "can you approve my expense report from the offsite",
    "what is the 401k match this year",
    "book me a conference room for friday afternoon",
]


def main():
    retriever = Retriever()
    hits = 0
    print("COVERAGE (expected article in top-3)")
    for question, expected in GOLDEN:
        results = retriever.search(question, k=3)
        found = any(chunk["article"] == expected for _, chunk in results)
        hits += 1 if found else 0
        top = results[0][1]["article"] if results else "no result"
        print("  [{s}] {q}  ->  {t}".format(s="ok" if found else "MISS", q=question, t=top))
    rate = hits / len(GOLDEN)

    print("\nREFUSAL (out-of-scope must fall below the grounding gate, score < {m})".format(m=MIN_SCORE))
    refusals = 0
    for question in OUT_OF_SCOPE:
        results = retriever.search(question, k=3)
        score = results[0][0] if results else 0.0
        refused = score < MIN_SCORE
        refusals += 1 if refused else 0
        print("  [{s}] {q}  (top score {v:.2f})".format(
            s="ok" if refused else "LEAK", q=question, v=score))

    print("\nhit rate: {h}/{n} = {r:.0%}   refusals: {f}/{o}".format(
        h=hits, n=len(GOLDEN), r=rate, f=refusals, o=len(OUT_OF_SCOPE)))

    if rate < 0.8 or refusals < len(OUT_OF_SCOPE):
        print("FAIL: below target")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
