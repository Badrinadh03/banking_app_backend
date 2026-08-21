import csv
import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.services import transfer_service

DISCLAIMER = "This is a portfolio/learning project, not a real bank or financial institution."


def get_statement_transactions(
    db: Session, user: User, account_id: int | None, start: date, end: date
) -> list[Transaction]:
    if account_id is not None:
        transactions = transfer_service.get_transaction_history(db, user, account_id)
    else:
        transactions = transfer_service.get_all_transactions_for_user(db, user)

    return [tx for tx in transactions if start <= tx.created_at.date() <= end]


def summarize_transactions(transactions: list[Transaction]) -> dict:
    spending = Decimal("0")
    income = Decimal("0")
    for tx in transactions:
        if tx.transaction_type == "deposit":
            income += tx.amount
        else:
            spending += tx.amount
    return {
        "spending": spending,
        "income": income,
        "cash_flow": income - spending,
        "count": len(transactions),
    }


def _transaction_row(tx: Transaction, account_id: int | None) -> dict:
    is_outgoing = (
        tx.from_account_id == account_id
        if account_id is not None
        else tx.transaction_type != "deposit"
    )
    is_external = tx.transaction_type == "external_transfer"

    if is_external:
        default_label = (
            f"Transfer to {tx.external_recipient_name or 'external account'}"
            if is_outgoing
            else "Transfer received"
        )
    elif tx.transaction_type == "deposit":
        default_label = "Deposit"
    else:
        default_label = "Transfer sent" if is_outgoing else "Transfer received"

    return {
        "date": tx.created_at,
        "description": tx.description or default_label,
        "type": tx.transaction_type,
        "is_outgoing": is_outgoing,
        "amount": tx.amount,
    }


def _account_label(account: Account | None) -> str:
    if account is None:
        return "All Accounts"
    return f"{account.account_type.capitalize()} #{account.account_number[-4:]}"


def generate_statement_csv(
    user: User, account: Account | None, transactions: list[Transaction], period_label: str
) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["Northline Bank Statement"])
    writer.writerow(["Account holder", user.full_name])
    writer.writerow(["Account", _account_label(account)])
    writer.writerow(["Period", period_label])
    writer.writerow([])
    writer.writerow(["Date", "Description", "Type", "Amount"])

    account_id = account.id if account else None
    for tx in transactions:
        row = _transaction_row(tx, account_id)
        signed_amount = -row["amount"] if row["is_outgoing"] else row["amount"]
        writer.writerow(
            [row["date"].strftime("%Y-%m-%d"), row["description"], row["type"], f"{signed_amount:.2f}"]
        )

    summary = summarize_transactions(transactions)
    writer.writerow([])
    writer.writerow(["Spending", f"{summary['spending']:.2f}"])
    writer.writerow(["Income", f"{summary['income']:.2f}"])
    writer.writerow(["Cash flow", f"{summary['cash_flow']:.2f}"])
    writer.writerow([])
    writer.writerow([DISCLAIMER])

    return buffer.getvalue().encode("utf-8")


def generate_statement_pdf(
    user: User, account: Account | None, transactions: list[Transaction], period_label: str
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    summary = summarize_transactions(transactions)
    account_id = account.id if account else None

    elements = [
        Paragraph("Northline Bank", styles["Title"]),
        Paragraph("Account Statement", styles["Heading2"]),
        Spacer(1, 0.15 * inch),
        Paragraph(f"Account holder: {user.full_name}", styles["Normal"]),
        Paragraph(f"Account: {_account_label(account)}", styles["Normal"]),
        Paragraph(f"Statement period: {period_label}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    summary_data = [
        ["Spending", "Income", "Cash flow"],
        [
            f"${summary['spending']:.2f}",
            f"${summary['income']:.2f}",
            f"${summary['cash_flow']:.2f}",
        ],
    ]
    summary_table = Table(summary_data, colWidths=[1.8 * inch] * 3)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d5dce6")),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    table_data = [["Date", "Description", "Type", "Amount"]]
    for tx in transactions:
        row = _transaction_row(tx, account_id)
        signed_amount = -row["amount"] if row["is_outgoing"] else row["amount"]
        sign = "-" if row["is_outgoing"] else "+"
        table_data.append(
            [
                row["date"].strftime("%Y-%m-%d"),
                row["description"],
                row["type"].replace("_", " ").title(),
                f"{sign}${abs(signed_amount):.2f}",
            ]
        )

    if len(table_data) == 1:
        elements.append(Paragraph("No transactions in this period.", styles["Normal"]))
    else:
        tx_table = Table(table_data, colWidths=[0.9 * inch, 2.7 * inch, 1.3 * inch, 1 * inch], repeatRows=1)
        tx_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d3a8f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d5dce6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(tx_table)

    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph(DISCLAIMER, styles["Italic"]))

    doc.build(elements)
    return buffer.getvalue()
