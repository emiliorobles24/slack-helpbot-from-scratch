"""Ticket escalation: the bot's honest exit.

When the KB does not cover a question, or the employee says the answer did
not help, the bot opens a ticket carrying the question plus what the bot
already tried, so the human agent starts warm instead of cold.

Mock mode (default): tickets are appended to tickets-outbox.jsonl so the
whole flow is testable with zero external accounts. Production swap: set the
JIRA_* variables and the same call creates a Jira issue in your project
through the platform REST API (standard library only, no extra dependency).
For a true JSM customer request that shows in the portal, point this at
POST /rest/servicedeskapi/request with a serviceDeskId and requestTypeId
instead; the interface here does not change.
"""

import base64
import json
import os
import time
import urllib.request

OUTBOX = os.path.join(os.path.dirname(__file__), "tickets-outbox.jsonl")


def _jira_configured():
    return all(
        os.environ.get(k) for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY")
    )


def create_ticket(summary, transcript, requester=None):
    """Create a ticket and return its key, e.g. IT-123 (or IT-MOCK-17 in mock mode)."""
    description = (
        "Opened by the Slack help bot after it could not resolve the question.\n\n"
        "Requester (Slack): {r}\n\nThread transcript:\n{t}".format(r=requester or "unknown", t=transcript)
    )
    if not _jira_configured():
        count = 0
        if os.path.exists(OUTBOX):
            with open(OUTBOX, encoding="utf-8") as f:
                count = sum(1 for _ in f)
        key = "IT-MOCK-{n}".format(n=count + 1)
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "key": key,
                        "summary": summary,
                        "description": description,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return key

    url = os.environ["JIRA_BASE_URL"].rstrip("/") + "/rest/api/3/issue"
    auth = base64.b64encode(
        "{u}:{t}".format(u=os.environ["JIRA_EMAIL"], t=os.environ["JIRA_API_TOKEN"]).encode()
    ).decode()
    payload = {
        "fields": {
            "project": {"key": os.environ["JIRA_PROJECT_KEY"]},
            "issuetype": {"name": os.environ.get("JIRA_ISSUE_TYPE", "Task")},
            "summary": summary[:250],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description[:30000]}]}
                ],
            },
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["key"]
