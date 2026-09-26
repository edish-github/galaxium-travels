from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import LoyaltyAccount, LoyaltyTier, LoyaltyTransaction, User
from schemas import ErrorResponse, LoyaltyAccountOut, LoyaltyTransactionOut


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _calculate_tier(lifetime_miles: int) -> str:
    if lifetime_miles >= 50000:
        return LoyaltyTier.STARLIGHT.value
    if lifetime_miles >= 25000:
        return LoyaltyTier.GOLD.value
    if lifetime_miles >= 10000:
        return LoyaltyTier.SILVER.value
    return LoyaltyTier.STANDARD.value


def enroll_user(db: Session, user_id: int) -> LoyaltyAccountOut | ErrorResponse:
    """Enroll an existing user into the Galaxium Loyalty program."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return ErrorResponse(
            error=f"User {user_id} not found",
            error_code="USER_NOT_FOUND",
            details="User must exist before enrolling in loyalty program",
        )

    existing = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if existing:
        return ErrorResponse(
            error=f"User {user_id} is already enrolled in loyalty program",
            error_code="ALREADY_ENROLLED",
            details="Duplicate loyalty account registration is not permitted",
        )

    now = _now_iso()
    account = LoyaltyAccount(
        user_id=user_id,
        tier=LoyaltyTier.STANDARD.value,
        miles_balance=1000,  # 1,000 welcome bonus miles
        lifetime_miles=1000,
        enrolled_at=now,
    )
    db.add(account)

    welcome_tx = LoyaltyTransaction(
        user_id=user_id,
        transaction_type="bonus",
        miles=1000,
        description="Welcome enrollment bonus",
        created_at=now,
    )
    db.add(welcome_tx)
    db.commit()
    db.refresh(account)

    return LoyaltyAccountOut.model_validate(account)


def get_loyalty_account(db: Session, user_id: int) -> LoyaltyAccountOut | ErrorResponse:
    """Retrieve loyalty account details for a user."""
    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not account:
        return ErrorResponse(
            error=f"Loyalty account for user {user_id} not found",
            error_code="LOYALTY_ACCOUNT_NOT_FOUND",
            details="User is not enrolled in the loyalty program",
        )
    return LoyaltyAccountOut.model_validate(account)


def award_miles(db: Session, user_id: int, miles: int, description: str) -> LoyaltyAccountOut | ErrorResponse:
    """Award miles to a loyalty account (e.g. from flight booking or promotion)."""
    if miles <= 0:
        return ErrorResponse(
            error="Miles to award must be positive",
            error_code="INVALID_MILES_AMOUNT",
            details=f"Received: {miles}",
        )

    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not account:
        return ErrorResponse(
            error=f"Loyalty account for user {user_id} not found",
            error_code="LOYALTY_ACCOUNT_NOT_FOUND",
            details="User is not enrolled in the loyalty program",
        )

    now = _now_iso()
    account.miles_balance += miles
    account.lifetime_miles += miles
    account.tier = _calculate_tier(account.lifetime_miles)

    tx = LoyaltyTransaction(
        user_id=user_id,
        transaction_type="accrual",
        miles=miles,
        description=description,
        created_at=now,
    )
    db.add(tx)
    db.commit()
    db.refresh(account)

    return LoyaltyAccountOut.model_validate(account)


def redeem_miles(db: Session, user_id: int, miles: int, description: str) -> LoyaltyAccountOut | ErrorResponse:
    """Redeem miles from a user's loyalty account."""
    if miles <= 0:
        return ErrorResponse(
            error="Miles to redeem must be positive",
            error_code="INVALID_MILES_AMOUNT",
            details=f"Received: {miles}",
        )

    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not account:
        return ErrorResponse(
            error=f"Loyalty account for user {user_id} not found",
            error_code="LOYALTY_ACCOUNT_NOT_FOUND",
            details="User is not enrolled in the loyalty program",
        )

    if account.miles_balance < miles:
        return ErrorResponse(
            error=f"Insufficient miles balance: available {account.miles_balance}, requested {miles}",
            error_code="INSUFFICIENT_MILES",
            details="Redemption requires sufficient available miles balance",
        )

    now = _now_iso()
    account.miles_balance -= miles

    tx = LoyaltyTransaction(
        user_id=user_id,
        transaction_type="redemption",
        miles=-miles,
        description=description,
        created_at=now,
    )
    db.add(tx)
    db.commit()
    db.refresh(account)

    return LoyaltyAccountOut.model_validate(account)


def get_transactions(db: Session, user_id: int) -> list[LoyaltyTransactionOut] | ErrorResponse:
    """Retrieve transaction history for a user's loyalty account."""
    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not account:
        return ErrorResponse(
            error=f"Loyalty account for user {user_id} not found",
            error_code="LOYALTY_ACCOUNT_NOT_FOUND",
            details="User is not enrolled in the loyalty program",
        )

    transactions = (
        db.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.user_id == user_id)
        .order_by(LoyaltyTransaction.transaction_id.desc())
        .all()
    )
    return [LoyaltyTransactionOut.model_validate(tx) for tx in transactions]
