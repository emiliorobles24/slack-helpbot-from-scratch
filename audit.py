"""Append-only audit ledger.

Every question, answer, escalation, and outcome writes one JSON line. This is
the same habit as the shared audit ledger in my n8n-support-ops workflows:
when someone asks "what did the bot tell people about VPN access last month"
or an auditor asks "show me every AI-generated answer", the evidence is a
filter on one file, not an archaeology project.

User IDs are hashed: the ledger needs "same person kept asking", never
"which person asked".
"""

import hashlib
import json
import os
import time

LEDGER_PATH = os.environ.get(
    "HELPBOT_LEDGER", os.path.join(os.path.dirname(__file__), "helpbot-ledger.jsonl")
)


def _hash_user(user_id):
    if not user_id:
        return None
    return hashlib.sha256(("helpbot:" + user_id).encode()).hexdigest()[:16]


def log(event, user_id=None, question=None, citations=None, outcome=None, extra=None):
    """event: asked | answered | not_covered | solved | ticket_created | error"""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": event,
        "user": _hash_user(user_id),
        "question": question,
        "citations": citations or [],
        "outcome": outcome,
    }
    if extra:
        record.update(extra)
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
