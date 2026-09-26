import pytest
from models import User
from schemas import ErrorResponse
from services import loyalty


@pytest.fixture
def test_user(db_session):
    user = User(name="Commander Shepard", email="shepard@normandy.space")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_enroll_user_success(db_session, test_user):
    result = loyalty.enroll_user(db_session, test_user.user_id)
    assert not isinstance(result, ErrorResponse)
    assert result.user_id == test_user.user_id
    assert result.tier == "standard"
    assert result.miles_balance == 1000  # Welcome bonus
    assert result.lifetime_miles == 1000


def test_enroll_user_duplicate_rejected(db_session, test_user):
    res1 = loyalty.enroll_user(db_session, test_user.user_id)
    assert not isinstance(res1, ErrorResponse)

    res2 = loyalty.enroll_user(db_session, test_user.user_id)
    assert isinstance(res2, ErrorResponse)
    assert res2.error_code == "ALREADY_ENROLLED"


def test_enroll_nonexistent_user(db_session):
    res = loyalty.enroll_user(db_session, 99999)
    assert isinstance(res, ErrorResponse)
    assert res.error_code == "USER_NOT_FOUND"


def test_award_miles_tier_progression(db_session, test_user):
    loyalty.enroll_user(db_session, test_user.user_id)

    # Award 10,000 miles -> Total 11,000 -> Silver
    res_silver = loyalty.award_miles(db_session, test_user.user_id, 10000, "Flight to Mars")
    assert not isinstance(res_silver, ErrorResponse)
    assert res_silver.tier == "silver"
    assert res_silver.miles_balance == 11000

    # Award 15,000 miles -> Total 26,000 -> Gold
    res_gold = loyalty.award_miles(db_session, test_user.user_id, 15000, "Flight to Europa")
    assert not isinstance(res_gold, ErrorResponse)
    assert res_gold.tier == "gold"

    # Award 25,000 miles -> Total 51,000 -> Starlight
    res_starlight = loyalty.award_miles(db_session, test_user.user_id, 25000, "Galactic expedition")
    assert not isinstance(res_starlight, ErrorResponse)
    assert res_starlight.tier == "starlight"


def test_award_miles_invalid_amount(db_session, test_user):
    loyalty.enroll_user(db_session, test_user.user_id)
    res = loyalty.award_miles(db_session, test_user.user_id, -500, "Invalid")
    assert isinstance(res, ErrorResponse)
    assert res.error_code == "INVALID_MILES_AMOUNT"


def test_redeem_miles_success_and_insufficient(db_session, test_user):
    loyalty.enroll_user(db_session, test_user.user_id)  # Starts with 1000 miles

    # Redeem 400 miles
    res = loyalty.redeem_miles(db_session, test_user.user_id, 400, "In-flight meal voucher")
    assert not isinstance(res, ErrorResponse)
    assert res.miles_balance == 600

    # Attempt to redeem 700 miles (more than available)
    res_fail = loyalty.redeem_miles(db_session, test_user.user_id, 700, "Cabin upgrade")
    assert isinstance(res_fail, ErrorResponse)
    assert res_fail.error_code == "INSUFFICIENT_MILES"
    assert res.miles_balance == 600  # Balance unchanged


def test_get_transactions_history(db_session, test_user):
    loyalty.enroll_user(db_session, test_user.user_id)  # bonus: 1000
    loyalty.award_miles(db_session, test_user.user_id, 2000, "Mars Hop")
    loyalty.redeem_miles(db_session, test_user.user_id, 500, "Seat reservation")

    txs = loyalty.get_transactions(db_session, test_user.user_id)
    assert not isinstance(txs, ErrorResponse)
    assert len(txs) == 3
    # Check most recent transaction first
    assert txs[0].transaction_type == "redemption"
    assert txs[0].miles == -500
    assert txs[1].transaction_type == "accrual"
    assert txs[1].miles == 2000
    assert txs[2].transaction_type == "bonus"
    assert txs[2].miles == 1000
