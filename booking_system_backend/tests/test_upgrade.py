import pytest
from models import Booking, Flight, LoyaltyAccount, User
from schemas import ErrorResponse
from services import upgrade


@pytest.fixture
def setup_flight_and_user(db_session):
    user = User(name="Garrus Vakarian", email="garrus@archangel.citadel")
    db_session.add(user)

    flight = Flight(
        origin="Earth",
        destination="Palaven",
        departure_time="2026-10-01 10:00",
        arrival_time="2026-10-01 18:00",
        base_price=500,
        economy_seats_available=50,
        business_seats_available=10,
        galaxium_seats_available=5,
    )
    db_session.add(flight)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(flight)

    booking = Booking(
        user_id=user.user_id,
        flight_id=flight.flight_id,
        status="booked",
        booking_time="2026-09-01 12:00",
        seat_class="economy",
        price_paid=500,
    )
    db_session.add(booking)

    loyalty_acc = LoyaltyAccount(
        user_id=user.user_id,
        tier="gold",
        miles_balance=15000,
        lifetime_miles=15000,
        enrolled_at="2026-01-01 00:00:00",
    )
    db_session.add(loyalty_acc)
    db_session.commit()
    db_session.refresh(booking)
    db_session.refresh(loyalty_acc)

    return user, flight, booking, loyalty_acc


def test_upgrade_economy_to_business_success(db_session, setup_flight_and_user):
    user, flight, booking, loyalty_acc = setup_flight_and_user

    res = upgrade.upgrade_seat_with_miles(
        db_session,
        booking_id=booking.booking_id,
        user_id=user.user_id,
        name=user.name,
        target_class="business",
    )

    assert not isinstance(res, ErrorResponse)
    assert res.previous_class == "economy"
    assert res.new_class == "business"
    assert res.miles_deducted == 5000
    assert res.status == "upgraded"

    # Verify inventory was updated
    db_session.refresh(flight)
    assert flight.economy_seats_available == 51  # Released back
    assert flight.business_seats_available == 9   # Consumed

    # Verify miles deducted
    db_session.refresh(loyalty_acc)
    assert loyalty_acc.miles_balance == 10000

    # Verify booking status
    db_session.refresh(booking)
    assert booking.seat_class == "business"


def test_upgrade_name_mismatch_rejected(db_session, setup_flight_and_user):
    user, flight, booking, _ = setup_flight_and_user

    res = upgrade.upgrade_seat_with_miles(
        db_session,
        booking_id=booking.booking_id,
        user_id=user.user_id,
        name="Wrong Impostor Name",
        target_class="business",
    )

    assert isinstance(res, ErrorResponse)
    assert res.error_code == "USER_MISMATCH"


def test_upgrade_insufficient_miles(db_session, setup_flight_and_user):
    user, flight, booking, loyalty_acc = setup_flight_and_user
    loyalty_acc.miles_balance = 2000  # Business upgrade requires 5000
    db_session.commit()

    res = upgrade.upgrade_seat_with_miles(
        db_session,
        booking_id=booking.booking_id,
        user_id=user.user_id,
        name=user.name,
        target_class="business",
    )

    assert isinstance(res, ErrorResponse)
    assert res.error_code == "INSUFFICIENT_MILES"


def test_upgrade_sold_out_target_class(db_session, setup_flight_and_user):
    user, flight, booking, _ = setup_flight_and_user
    flight.business_seats_available = 0
    db_session.commit()

    res = upgrade.upgrade_seat_with_miles(
        db_session,
        booking_id=booking.booking_id,
        user_id=user.user_id,
        name=user.name,
        target_class="business",
    )

    assert isinstance(res, ErrorResponse)
    assert res.error_code == "SEATS_UNAVAILABLE"


def test_upgrade_already_in_class(db_session, setup_flight_and_user):
    user, flight, booking, _ = setup_flight_and_user

    res = upgrade.upgrade_seat_with_miles(
        db_session,
        booking_id=booking.booking_id,
        user_id=user.user_id,
        name=user.name,
        target_class="economy",
    )

    assert isinstance(res, ErrorResponse)
    assert res.error_code == "ALREADY_IN_CLASS"
