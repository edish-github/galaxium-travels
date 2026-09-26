from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import Booking, Flight, LoyaltyAccount, LoyaltyTransaction, User
from schemas import ErrorResponse, SeatUpgradeOut

UPGRADE_MILES_COST = {
    ("economy", "business"): 5000,
    ("economy", "galaxium"): 12000,
    ("business", "galaxium"): 7000,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def upgrade_seat_with_miles(
    db: Session,
    booking_id: int,
    user_id: int,
    name: str,
    target_class: str,
) -> SeatUpgradeOut | ErrorResponse:
    """Upgrade a booking's seat class using accumulated loyalty miles."""
    # 1. Validate user existence and name match (standard Galaxium security pattern)
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return ErrorResponse(
            error=f"User {user_id} not found",
            error_code="USER_NOT_FOUND",
        )
    if user.name.lower() != name.lower():
        return ErrorResponse(
            error=f"User name mismatch for user {user_id}",
            error_code="USER_MISMATCH",
            details="Provided name does not match user account records",
        )

    # 2. Validate booking
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        return ErrorResponse(
            error=f"Booking {booking_id} not found",
            error_code="BOOKING_NOT_FOUND",
        )
    if booking.user_id != user_id:
        return ErrorResponse(
            error=f"Booking {booking_id} does not belong to user {user_id}",
            error_code="UNAUTHORIZED_BOOKING_ACCESS",
        )
    if booking.status != "booked":
        return ErrorResponse(
            error=f"Cannot upgrade booking with status '{booking.status}'",
            error_code="INVALID_BOOKING_STATUS",
            details="Only confirmed active bookings may be upgraded",
        )

    current_class = booking.seat_class.lower()
    target = target_class.lower()

    if current_class == target:
        return ErrorResponse(
            error=f"Booking is already in class '{target}'",
            error_code="ALREADY_IN_CLASS",
            details="Target seat class must differ from current class",
        )

    upgrade_pair = (current_class, target)
    if upgrade_pair not in UPGRADE_MILES_COST:
        return ErrorResponse(
            error=f"Invalid upgrade path from '{current_class}' to '{target}'",
            error_code="INVALID_UPGRADE_PATH",
            details="Cabin downgrades or unsupported seat upgrades are not allowed",
        )

    required_miles = UPGRADE_MILES_COST[upgrade_pair]

    # 3. Validate loyalty account & balance
    loyalty_acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not loyalty_acc:
        return ErrorResponse(
            error=f"User {user_id} does not have a loyalty account",
            error_code="LOYALTY_ACCOUNT_NOT_FOUND",
            details="Seat upgrades via miles require an active loyalty membership",
        )
    if loyalty_acc.miles_balance < required_miles:
        return ErrorResponse(
            error=f"Insufficient miles: required {required_miles}, available {loyalty_acc.miles_balance}",
            error_code="INSUFFICIENT_MILES",
            details="Upgrade requires sufficient loyalty miles",
        )

    # 4. Validate flight inventory
    flight = db.query(Flight).filter(Flight.flight_id == booking.flight_id).first()
    if not flight:
        return ErrorResponse(
            error=f"Flight {booking.flight_id} not found",
            error_code="FLIGHT_NOT_FOUND",
        )

    target_seats = (
        flight.business_seats_available
        if target == "business"
        else flight.galaxium_seats_available
    )
    if target_seats <= 0:
        return ErrorResponse(
            error=f"No seats available in target class '{target}' for flight {flight.flight_id}",
            error_code="SEATS_UNAVAILABLE",
            details=f"Cabin '{target}' is sold out",
        )

    # 5. Apply inventory update
    if current_class == "economy":
        flight.economy_seats_available += 1
    elif current_class == "business":
        flight.business_seats_available += 1

    if target == "business":
        flight.business_seats_available -= 1
    elif target == "galaxium":
        flight.galaxium_seats_available -= 1

    # 6. Deduct miles and create transaction
    now = _now_iso()
    loyalty_acc.miles_balance -= required_miles
    tx = LoyaltyTransaction(
        user_id=user_id,
        transaction_type="redemption",
        miles=-required_miles,
        description=f"Seat upgrade on flight {flight.flight_id} to {target}",
        created_at=now,
    )
    db.add(tx)

    # 7. Update booking
    booking.seat_class = target
    db.commit()
    db.refresh(booking)

    return SeatUpgradeOut(
        booking_id=booking.booking_id,
        user_id=booking.user_id,
        flight_id=booking.flight_id,
        previous_class=current_class,
        new_class=target,
        miles_deducted=required_miles,
        status="upgraded",
    )
