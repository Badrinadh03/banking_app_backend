import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Compressed interval so recurring payments and check-deposit holds are
# actually observable in a demo/testing session, rather than requiring a
# real multi-day wait — the same "accelerated but honest" pattern already
# used elsewhere in this app (e.g. the 2-minute check-deposit hold itself).
JOB_INTERVAL_SECONDS = 60

scheduler = AsyncIOScheduler()


def _run_due_recurring_payments() -> None:
    from app.services import recurring_payment_service

    db = SessionLocal()
    try:
        recurring_payment_service.process_due_payments(db)
    except Exception:
        logger.exception("Failed to process due recurring payments")
    finally:
        db.close()


def _run_check_deposit_holds() -> None:
    from app.services import check_deposit_service

    db = SessionLocal()
    try:
        check_deposit_service.clear_due_holds(db)
    except Exception:
        logger.exception("Failed to clear due check-deposit holds")
    finally:
        db.close()


def start_scheduler() -> None:
    # Never run against the real DB while pytest is driving the app through
    # its own isolated in-memory session — same spirit as the
    # disable_real_email_sending test fixture avoiding real side effects.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    if scheduler.running:
        return
    scheduler.add_job(_run_due_recurring_payments, "interval", seconds=JOB_INTERVAL_SECONDS)
    scheduler.add_job(_run_check_deposit_holds, "interval", seconds=JOB_INTERVAL_SECONDS)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
