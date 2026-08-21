from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.fraud_alert import FraudAlertRead
from app.services import fraud_service

router = APIRouter(prefix="/fraud-alerts", tags=["fraud-alerts"])


@router.get("", response_model=list[FraudAlertRead])
def list_fraud_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return fraud_service.list_for_user(db, current_user)


@router.post("/{alert_id}/acknowledge", response_model=FraudAlertRead)
def acknowledge_fraud_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return fraud_service.acknowledge(db, current_user, alert_id)
