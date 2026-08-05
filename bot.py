"""The Slack surface: Bolt app in Socket Mode.

Socket Mode means no public URL, no ngrok, no firewall change: the app opens
an outbound websocket to Slack, which is the right dev posture and fine for
an internal tool in production too.

Conversation shape:
- @helpbot in a channel, or a DM, asks the question
- the bot answers in a thread with citations, plus two buttons:
  "That solved it" and "Still stuck, open a ticket"
- solved  -> logged as a deflection (this is the number the program reports)
- stuck   -> ticket created carrying the question and the bot's answer,
  key posted back to the thread
- every step writes to the audit ledger

Escalation context travels WITH the escalation: the question rides in the
ticket button's value and the answer is the message the button sits on, so
no history scopes are needed and the flow works identically in channels and
DMs. Least privilege stays honest because the code never needs to read
anything beyond what was addressed to the bot.
"""

import json
import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import audit
import tickets
from answer import answer
from rag import Retriever

app = App(token=os.environ["SLACK_BOT_TOKEN"])
retriever = Retriever()  # build the index once at startup

_MENTION = re.compile(r"<@[A-Z0-9]+>")


def _blocks(result, question):
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": result["text"]}}]
    if result["citations"]:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Sources: " + ", ".join(result["citations"])}
                ],
            }
        )
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "That solved it"},
                    "style": "primary",
                    "action_id": "helpbot_solved",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Still stuck, open a ticket"},
                    "action_id": "helpbot_ticket",
                    # the question travels with the button (2000-char limit),
                    # so escalation needs no history scopes
                    "value": json.dumps({"q": question[:1800]}),
                },
            ],
        }
    )
    return blocks


def _handle_question(text, user, say, thread_ts):
    audit.log("asked", user_id=user, question=text)
    result = answer(text, retriever=retriever)
    event = "answered" if result["grounded"] else "not_covered"
    audit.log(event, user_id=user, question=text, citations=result["citations"],
              extra={"mode": result["mode"]})
    say(text=result["text"], blocks=_blocks(result, text), thread_ts=thread_ts)


@app.event("app_mention")
def on_mention(event, say):
    # strip the bot mention wherever it appears; words before it survive
    question = _MENTION.sub(" ", event.get("text", "")).strip()
    _handle_question(question, event.get("user"), say, event.get("thread_ts") or event.get("ts"))


@app.event("message")
def on_dm(event, say):
    if event.get("channel_type") != "im" or event.get("bot_id") or event.get("subtype"):
        return
    _handle_question(event.get("text", ""), event.get("user"),
                     say, event.get("thread_ts") or event.get("ts"))


@app.action("helpbot_solved")
def on_solved(ack, body, say):
    ack()
    user = body["user"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    audit.log("solved", user_id=user, outcome="deflected")
    say(text="Great. Logged as solved, no ticket needed.", thread_ts=thread_ts)


@app.action("helpbot_ticket")
def on_ticket(ack, body, say):
    ack()
    user = body["user"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    # The agent should see the question AND what the bot already suggested,
    # and nobody should repeat themselves to a human. Both travel with the
    # interaction itself: the question in the button value, the answer in the
    # message the button was attached to. No history reads required.
    try:
        question = json.loads(body["actions"][0].get("value") or "{}").get("q", "")
    except (ValueError, KeyError, IndexError):
        question = ""
    bot_answer = body["message"].get("text", "")
    transcript = "[employee] {q}\n[helpbot] {a}".format(q=question or "(unknown)", a=bot_answer)
    try:
        key = tickets.create_ticket(
            summary="Helpbot escalation: " + (question[:120] or "Slack conversation"),
            transcript=transcript,
            requester=user,
        )
    except Exception as exc:  # a broken ticket backend must never eat an escalation silently
        audit.log("error", user_id=user, question=question, outcome=str(exc))
        say(text="I could not reach the ticket system just now. Please contact IT directly "
                 "and mention what you tried here.", thread_ts=thread_ts)
        return
    audit.log("ticket_created", user_id=user, question=question, outcome=key)
    say(text="Opened *{k}* carrying your question and what I already suggested. "
             "A human has it from here.".format(k=key),
        thread_ts=thread_ts)


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
