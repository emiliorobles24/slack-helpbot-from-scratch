"""Grounded answering: cite or refuse.

Two modes behind one interface:

- Extractive mode (no API key): returns the best-matching KB section verbatim
  with its citation. Zero dependencies, so the whole pipeline is testable
  offline and in CI.
- Model mode (ANTHROPIC_API_KEY set): Claude writes a conversational answer
  that may ONLY use the retrieved sections, must cite them, and must refuse
  when the KB does not cover the question. The refusal is a feature: a wrong
  answer costs more trust than a ticket.
"""

import os

from rag import Retriever

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# Below this BM25 score the KB almost certainly does not cover the question;
# escalate instead of letting the model improvise. Set from the eval set's
# score distribution: in-scope questions bottom out around 6, out-of-scope
# noise (a stray word matching one article) tops out around 4.
MIN_SCORE = 5.0

NOT_COVERED = (
    "I could not find this in the help center, so I will not guess. "
    "Use the button below to open a ticket and a human will take it from here."
)

SYSTEM = """You are an IT help bot inside a company Slack workspace. Answer the \
employee's question using ONLY the knowledge-base sections provided in the user \
message. Rules, in priority order:

1. If the sections do not answer the question, say exactly: NOT_COVERED
2. Never invent steps, links, settings, or policy. If a detail is not in the \
sections, it does not exist for you.
3. If the question involves a security concern (compromised account, phishing, \
lost device), lead with the urgent path from the sections before anything else.
4. Cite every section you used at the end of the answer on one line, formatted \
exactly like: Sources: kb/example.md
5. Keep it tight: a Slack message someone can act on in under a minute, plain \
text, numbered steps only when order matters."""


def _format_context(hits):
    blocks = []
    for score, chunk in hits:
        blocks.append(
            "SECTION (article: {a}, heading: {h})\n{t}".format(
                a=chunk["article"], h=chunk["heading"], t=chunk["text"]
            )
        )
    return "\n\n---\n\n".join(blocks)


def _extractive(question, hits):
    score, best = hits[0]
    text = "*{h}* (from {a})\n\n{t}".format(h=best["heading"], a=best["article"], t=best["text"])
    return {
        "text": text,
        "citations": [best["article"]],
        "grounded": True,
        "mode": "extractive",
    }


def _model_answer(question, hits):
    import anthropic  # imported lazily so extractive mode needs no install

    client = anthropic.Anthropic()
    context = _format_context(hits)
    # Server-side fallback: if a safety classifier declines the request, the
    # API retries it on Anthropic's recommended fallback model in the same
    # call instead of surfacing the refusal to the employee.
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2048,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": "Knowledge-base sections:\n\n{c}\n\nEmployee question: {q}".format(
                    c=context, q=question
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        return {"text": NOT_COVERED, "citations": [], "grounded": False, "mode": "model"}
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if "NOT_COVERED" in text:
        return {"text": NOT_COVERED, "citations": [], "grounded": False, "mode": "model"}
    cited = [c["article"] for _, c in hits if c["article"] in text]
    return {
        "text": text,
        "citations": sorted(set(cited)),
        "grounded": True,
        "mode": "model",
    }


def answer(question, retriever=None):
    """Answer a question from the KB, or refuse with an escalation path.

    Returns {text, citations, grounded, mode}. grounded=False means the bot
    is declining and the caller should offer ticket creation.
    """
    retriever = retriever or Retriever()
    hits = retriever.search(question, k=3)
    if not hits or hits[0][0] < MIN_SCORE:
        return {"text": NOT_COVERED, "citations": [], "grounded": False, "mode": "gate"}
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _model_answer(question, hits)
    return _extractive(question, hits)
