import json
from datetime import datetime
from decimal import Decimal

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BadRequestError
from app.models.chat_message import ChatMessage
from app.models.payee import Payee
from app.models.user import User
from app.services import (
    account_service,
    budget_service,
    fraud_service,
    recurring_payment_service,
    savings_goal_service,
    transfer_service,
)

MODEL = "claude-sonnet-5"
MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDS = 5

# The only pages the assistant is allowed to point users to — keeps
# suggest_action from ever linking somewhere that doesn't exist.
VALID_PATHS = {
    "/": "Accounts",
    "/transfer-money": "Transfer money",
    "/pay-bills": "Pay Bills",
    "/zelle": "Zelle",
    "/wire-ach": "Wire / ACH",
    "/recurring-payments": "Recurring Payments",
    "/spending": "Spending & Budgets",
    "/deposit-checks": "Deposit Checks",
    "/beneficiaries": "Beneficiaries",
    "/security-center": "Security Center",
    "/cards": "Cards",
    "/statements": "Statements",
}

SYSTEM_PROMPT = f"""You are Northline Assistant, the in-app virtual assistant for Northline Bank \
(a portfolio/learning project, not a real bank).

Rules you must follow:
- Only state financial facts (balances, transactions, goals, budgets, bills, alerts) that came \
from a tool result earlier in this conversation. Never invent or estimate numbers.
- You cannot move money, open or close accounts, or change any settings yourself — you have no \
tools that do that. If the user wants to do something like that, call suggest_action to point \
them to the right page instead of pretending to perform it.
- Valid paths for suggest_action are exactly: {", ".join(f'{p} ({label})' for p, label in VALID_PATHS.items())}. \
Never suggest a path outside this list.
- Whenever you call suggest_action, always also write a short sentence of reply text in the same \
turn explaining what you're pointing them to — never send a suggest_action call with no \
accompanying text. Only call suggest_action when the user's current message actually calls for \
it — don't repeat a suggestion from earlier in the conversation unless they ask again.
- Keep replies short and conversational, like a real bank chat assistant — a sentence or two, \
not a report. Use tools proactively when a question needs real data instead of guessing.
- If asked something unrelated to this bank account (general knowledge, other companies, etc.), \
politely redirect to what you can help with here.
"""

TOOLS = [
    {
        "name": "get_accounts",
        "description": "Get the user's bank accounts with type, balance, and status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_transactions",
        "description": "Get the user's most recent transactions, optionally filtered to one account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "Optional account id to filter to"},
                "limit": {"type": "integer", "description": "Max transactions to return (default 10, max 25)"},
            },
        },
    },
    {
        "name": "get_spending_summary",
        "description": "Get total spending and income for a given month (defaults to the current month).",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer", "description": "1-12"},
            },
        },
    },
    {
        "name": "get_budgets",
        "description": "Get the user's monthly budgets and how much of each has been spent this month.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_savings_goals",
        "description": "Get the user's savings goals and real progress toward each.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_upcoming_bills",
        "description": "Get the user's active recurring/scheduled payments (transfers, bill pay, or Zelle).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_security_alerts",
        "description": "Get the user's unacknowledged security/fraud alerts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "suggest_action",
        "description": (
            "Attach a quick-action button to your reply that deep-links the user to a page in "
            "the app to complete a task themselves, e.g. transferring money or paying a bill. "
            "You cannot perform these actions yourself — always use this instead of claiming you did."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "enum": list(VALID_PATHS.keys())},
                "label": {"type": "string", "description": "Short button label, e.g. 'Go to Transfer'"},
            },
            "required": ["path"],
        },
    },
]


def _get_client() -> Anthropic:
    if not settings.assistant_enabled:
        raise BadRequestError(
            "The assistant isn't configured yet — add ANTHROPIC_API_KEY to the backend .env to enable it."
        )
    return Anthropic(api_key=settings.anthropic_api_key)


def _execute_tool(db: Session, user: User, name: str, tool_input: dict) -> dict:
    if name == "get_accounts":
        accounts = account_service.list_accounts(db, user)
        return {
            "accounts": [
                {
                    "id": a.id,
                    "type": a.account_type,
                    "last4": a.account_number[-4:],
                    "balance": str(a.balance),
                    "status": a.status,
                }
                for a in accounts
            ]
        }

    if name == "get_recent_transactions":
        limit = min(int(tool_input.get("limit") or 10), 25)
        account_id = tool_input.get("account_id")
        if account_id:
            account = account_service.get_account_for_user(db, user, int(account_id))
            txs = transfer_service.get_transaction_history(db, user, account.id)
        else:
            txs = transfer_service.get_all_transactions_for_user(db, user)
        txs = sorted(txs, key=lambda t: t.created_at, reverse=True)[:limit]
        return {
            "transactions": [
                {
                    "type": t.transaction_type,
                    "amount": str(t.amount),
                    "description": t.description,
                    "date": t.created_at.isoformat(),
                }
                for t in txs
            ]
        }

    if name == "get_spending_summary":
        now = datetime.now()
        year = int(tool_input.get("year") or now.year)
        month = int(tool_input.get("month") or now.month)
        txs = transfer_service.get_all_transactions_for_user(db, user)
        spending = Decimal("0")
        income = Decimal("0")
        for t in txs:
            if t.created_at.year != year or t.created_at.month != month:
                continue
            if t.transaction_type == "deposit":
                income += t.amount
            else:
                spending += t.amount
        return {
            "year": year, "month": month,
            "spending": str(spending), "income": str(income),
            "cash_flow": str(income - spending),
        }

    if name == "get_budgets":
        now = datetime.now()
        progress = budget_service.get_progress(db, user, now.year, now.month)
        return {
            "budgets": [
                {
                    "category": p["budget"].category,
                    "monthly_limit": str(p["budget"].monthly_limit),
                    "spent_this_month": str(p["spent"]),
                    "percent_used": round(p["percent_used"], 1),
                }
                for p in progress
            ]
        }

    if name == "get_savings_goals":
        goals = savings_goal_service.list_for_user(db, user)
        return {
            "savings_goals": [
                {
                    "name": g.name,
                    "target_amount": str(g.target_amount),
                    "current_balance": str(g.account.balance),
                    "percent_complete": round(
                        float(min(g.account.balance / g.target_amount, 1) * 100) if g.target_amount else 0.0, 1
                    ),
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                }
                for g in goals
            ]
        }

    if name == "get_upcoming_bills":
        recurring = [r for r in recurring_payment_service.list_for_user(db, user) if r.is_active]
        results = []
        for r in recurring:
            target = None
            if r.payment_type == "bill_pay" and r.payee_id:
                payee = db.get(Payee, r.payee_id)
                target = payee.nickname if payee else None
            elif r.payment_type == "zelle":
                target = r.zelle_contact
            results.append(
                {
                    "type": r.payment_type,
                    "amount": str(r.amount),
                    "frequency": r.frequency,
                    "next_run_date": r.next_run_date.isoformat(),
                    "target": target,
                }
            )
        return {"upcoming_bills": results}

    if name == "get_security_alerts":
        alerts = [a for a in fraud_service.list_for_user(db, user) if not a.acknowledged]
        return {
            "security_alerts": [
                {"rule": a.rule, "message": a.message, "date": a.created_at.isoformat()} for a in alerts
            ]
        }

    return {"error": f"Unknown tool {name}"}


def send_message(db: Session, user: User, content: str) -> ChatMessage:
    client = _get_client()

    user_message = ChatMessage(user_id=user.id, role="user", content=content)
    db.add(user_message)
    db.commit()

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    history.reverse()
    messages = [{"role": m.role, "content": m.content} for m in history]

    suggested_actions: list[dict] = []
    text_parts: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages
        )

        # A single turn can carry both explanatory text and a tool call (e.g.
        # "Head to Zelle for that." + a suggest_action call) — collect text
        # from every turn, not just the final one, or that text is lost.
        text_parts.extend(block.text for block in response.content if block.type == "text")

        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "suggest_action":
                path = block.input.get("path")
                if path in VALID_PATHS:
                    suggested_actions.append(
                        {"label": block.input.get("label") or VALID_PATHS[path], "path": path}
                    )
                result = {"ok": True}
            else:
                result = _execute_tool(db, user, block.name, block.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)}
            )
        messages.append({"role": "user", "content": tool_results})

    final_text = "".join(text_parts).strip()
    if not final_text:
        final_text = "Here's where you can do that:" if suggested_actions else (
            "Sorry, I'm having trouble with that request right now."
        )

    assistant_message = ChatMessage(
        user_id=user.id,
        role="assistant",
        content=final_text,
        suggested_actions=suggested_actions or None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def list_for_user(db: Session, user: User, limit: int = 100) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )


def clear_for_user(db: Session, user: User) -> None:
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete()
    db.commit()
