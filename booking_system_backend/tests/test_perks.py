import pytest
from models import LoyaltyAccount, User
from schemas import ErrorResponse
from services import perks


@pytest.fixture
def test_user(db_session):
    user = User(name="Liara TSoni", email="liara@shadowbroker.net")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_get_tier_perks():
    standard = perks.get_tier_perks("standard")
    assert not standard.lounge_access
    assert standard.free_checked_bags == 1
    assert standard.discount_percentage == 0

    silver = perks.get_tier_perks("silver")
    assert not silver.lounge_access
    assert silver.free_checked_bags == 2
    assert silver.discount_percentage == 5

    gold = perks.get_tier_perks("gold")
    assert gold.lounge_access
    assert gold.free_checked_bags == 3
    assert gold.discount_percentage == 10

    starlight = perks.get_tier_perks("starlight")
    assert starlight.lounge_access
    assert starlight.free_checked_bags == 4
    assert starlight.discount_percentage == 15


def test_calculate_baggage_unenrolled_user(db_session, test_user):
    # Unenrolled defaults to standard: 1 free bag for economy
    calc1 = perks.calculate_baggage(db_session, test_user.user_id, "economy", 1)
    assert not isinstance(calc1, ErrorResponse)
    assert calc1.free_bags_allowed == 1
    assert calc1.charged_bags == 0
    assert calc1.baggage_fee == 0

    # 3 bags on economy -> 2 charged
    calc2 = perks.calculate_baggage(db_session, test_user.user_id, "economy", 3)
    assert not isinstance(calc2, ErrorResponse)
    assert calc2.free_bags_allowed == 1
    assert calc2.charged_bags == 2
    assert calc2.baggage_fee == 150  # 2 * 75


def test_calculate_baggage_tier_benefit(db_session, test_user):
    # Enroll user as Gold (3 free bags)
    acc = LoyaltyAccount(
        user_id=test_user.user_id,
        tier="gold",
        miles_balance=30000,
        lifetime_miles=30000,
        enrolled_at="2026-01-01 00:00:00",
    )
    db_session.add(acc)
    db_session.commit()

    # Economy normally allows 1 free bag, but Gold allows 3
    calc = perks.calculate_baggage(db_session, test_user.user_id, "economy", 3)
    assert not isinstance(calc, ErrorResponse)
    assert calc.free_bags_allowed == 3
    assert calc.charged_bags == 0
    assert calc.baggage_fee == 0

    # 4 bags -> 1 charged
    calc_extra = perks.calculate_baggage(db_session, test_user.user_id, "economy", 4)
    assert calc_extra.charged_bags == 1
    assert calc_extra.baggage_fee == 75


def test_calculate_baggage_invalid_count(db_session, test_user):
    res = perks.calculate_baggage(db_session, test_user.user_id, "economy", -2)
    assert isinstance(res, ErrorResponse)
    assert res.error_code == "INVALID_BAG_COUNT"
