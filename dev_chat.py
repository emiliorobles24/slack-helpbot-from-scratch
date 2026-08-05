"""Terminal chat mode: the whole pipeline with no Slack and no API keys.

Run `python3 dev_chat.py` and ask IT questions. Retrieval, grounding gate,
citations, escalation, and the audit ledger all behave exactly as they do in
Slack; only the surface differs. This is how the pipeline gets developed and
demoed without touching a workspace.
"""

import audit
import tickets
from answer import answer
from rag import Retriever


def main():
    retriever = Retriever()
    print("helpbot dev chat. Ask an IT question, or 'quit'.")
    print("(no ANTHROPIC_API_KEY set -> extractive mode; set one for model answers)\n")
    while True:
        try:
            question = input("you> ").strip()
        except EOFError:
            break
        if not question or question.lower() in ("quit", "exit"):
            break
        audit.log("asked", user_id="dev", question=question)
        result = answer(question, retriever=retriever)
        print("\nhelpbot [{m}]>".format(m=result["mode"]))
        print(result["text"])
        if result["citations"]:
            print("\nSources: " + ", ".join(result["citations"]))
        if not result["grounded"]:
            choice = input("\nOpen a ticket? [y/N] ").strip().lower()
            if choice == "y":
                key = tickets.create_ticket(
                    summary="Helpbot escalation: " + question[:120],
                    transcript="[employee] " + question,
                    requester="dev",
                )
                audit.log("ticket_created", user_id="dev", question=question, outcome=key)
                print("Opened {k} (mock outbox unless JIRA_* is configured).".format(k=key))
        audit.log(
            "answered" if result["grounded"] else "not_covered",
            user_id="dev", question=question, citations=result["citations"],
            extra={"mode": result["mode"]},
        )
        print()


if __name__ == "__main__":
    main()
