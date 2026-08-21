from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    accounts,
    addresses,
    assistant,
    auth,
    beneficiaries,
    billpay,
    budgets,
    cards,
    check_deposits,
    fraud_alerts,
    notifications,
    payees,
    recurring,
    savings_goals,
    statements,
    transactions,
    transfers,
    users,
    zelle,
    zipcodes,
)
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Banking App API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(transfers.router)
app.include_router(transactions.router)
app.include_router(notifications.router)
app.include_router(statements.router)
app.include_router(payees.router)
app.include_router(billpay.router)
app.include_router(zelle.router)
app.include_router(zipcodes.router)
app.include_router(addresses.router)
app.include_router(cards.router)
app.include_router(recurring.router)
app.include_router(budgets.router)
app.include_router(savings_goals.router)
app.include_router(beneficiaries.router)
app.include_router(check_deposits.router)
app.include_router(fraud_alerts.router)
app.include_router(assistant.router)


@app.get("/health")
def health():
    return {"status": "ok"}
