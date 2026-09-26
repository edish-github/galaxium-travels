import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Booking, Flight, User


class TestLoyaltyEndpoints:
    """Test loyalty REST endpoints."""

    def test_enroll_loyalty_and_get_account(self, client, db_session):
        user = User(name="Tali Zorah", email="tali@quarian.fleet")
        db_session.add(user)
        db_session.commit()

        # Enroll
        res = client.post("/loyalty/enroll", json={"user_id": user.user_id})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == user.user_id
        assert data["tier"] == "standard"
        assert data["miles_balance"] == 1000

        # Duplicate enrollment should return 400
        dup_res = client.post("/loyalty/enroll", json={"user_id": user.user_id})
        assert dup_res.status_code == 400
        assert dup_res.json()["error_code"] == "ALREADY_ENROLLED"

        # Get account
        get_res = client.get(f"/loyalty/{user.user_id}")
        assert get_res.status_code == 200
        assert get_res.json()["user_id"] == user.user_id

    def test_get_transactions_and_perks(self, client, db_session):
        user = User(name="Urdnot Wrex", email="wrex@tuchanka.clan")
        db_session.add(user)
        db_session.commit()

        client.post("/loyalty/enroll", json={"user_id": user.user_id})

        # Check transactions
        tx_res = client.get(f"/loyalty/{user.user_id}/transactions")
        assert tx_res.status_code == 200
        txs = tx_res.json()
        assert len(txs) >= 1
        assert txs[0]["transaction_type"] == "bonus"

        # Check perks
        perks_res = client.get(f"/loyalty/{user.user_id}/perks")
        assert perks_res.status_code == 200
        perks_data = perks_res.json()
        assert perks_data["tier"] == "standard"
        assert not perks_data["lounge_access"]

    def test_calculate_baggage_endpoint(self, client, db_session):
        user = User(name="Kaiden Alenko", email="kaiden@alliance.navy")
        db_session.add(user)
        db_session.commit()

        client.post("/loyalty/enroll", json={"user_id": user.user_id})

        calc_res = client.post("/loyalty/baggage/calculate", json={
            "user_id": user.user_id,
            "seat_class": "economy",
            "number_of_bags": 3,
        })
        assert calc_res.status_code == 200
        baggage_data = calc_res.json()
        assert baggage_data["free_bags_allowed"] == 1
        assert baggage_data["charged_bags"] == 2
        assert baggage_data["baggage_fee"] == 150

    def test_upgrade_booking_endpoint(self, client, db_session):
        user = User(name="Ashley Williams", email="ashley@alliance.mil")
        db_session.add(user)

        flight = Flight(
            origin="Earth",
            destination="Eden Prime",
            departure_time="2099-05-01 08:00",
            arrival_time="2099-05-01 16:00",
            base_price=600,
            economy_seats_available=40,
            business_seats_available=8,
            galaxium_seats_available=2,
        )
        db_session.add(flight)
        db_session.commit()

        # Enroll user and award miles
        client.post("/loyalty/enroll", json={"user_id": user.user_id})
        from services import loyalty
        loyalty.award_miles(db_session, user.user_id, 10000, "Bonus miles")

        # Create booking
        booking = Booking(
            user_id=user.user_id,
            flight_id=flight.flight_id,
            status="booked",
            booking_time="2099-04-10 10:00",
            seat_class="economy",
            price_paid=600,
        )
        db_session.add(booking)
        db_session.commit()

        # Upgrade booking
        upgrade_res = client.post(f"/bookings/{booking.booking_id}/upgrade", json={
            "user_id": user.user_id,
            "name": user.name,
            "target_class": "business",
        })
        assert upgrade_res.status_code == 200
        data = upgrade_res.json()
        assert data["previous_class"] == "economy"
        assert data["new_class"] == "business"
        assert data["miles_deducted"] == 5000
