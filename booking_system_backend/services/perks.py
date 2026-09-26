from sqlalchemy.orm import Session

from models import LoyaltyAccount, LoyaltyTier
from schemas import BaggageCalculationOut, ErrorResponse, PerksSummaryOut

# Baggage allowances by seat class (base)
CLASS_FREE_BAGS = {
    "economy": 1,
    "business": 2,
    "galaxium": 3,
}

# Baggage allowances by loyalty tier
TIER_FREE_BAGS = {
    LoyaltyTier.STANDARD.value: 1,
    LoyaltyTier.SILVER.value: 2,
    LoyaltyTier.GOLD.value: 3,
    LoyaltyTier.STARLIGHT.value: 4,
}

# Excess baggage fee per additional piece
EXCESS_BAG_FEE = 75


def get_tier_perks(tier: str) -> PerksSummaryOut:
    """Return tier perks including lounge access, boarding group, and booking discount."""
    t = tier.lower()
    if t == LoyaltyTier.STARLIGHT.value:
        return PerksSummaryOut(
            tier=t,
            lounge_access=True,
            priority_boarding_group="Group 1 (First Class / Starlight)",
            free_checked_bags=4,
            discount_percentage=15,
        )
    if t == LoyaltyTier.GOLD.value:
        return PerksSummaryOut(
            tier=t,
            lounge_access=True,
            priority_boarding_group="Group 2 (Gold Priority)",
            free_checked_bags=3,
            discount_percentage=10,
        )
    if t == LoyaltyTier.SILVER.value:
        return PerksSummaryOut(
            tier=t,
            lounge_access=False,
            priority_boarding_group="Group 3 (Silver Priority)",
            free_checked_bags=2,
            discount_percentage=5,
        )
    return PerksSummaryOut(
        tier=LoyaltyTier.STANDARD.value,
        lounge_access=False,
        priority_boarding_group="Group 4 (General)",
        free_checked_bags=1,
        discount_percentage=0,
    )


def calculate_baggage(
    db: Session,
    user_id: int,
    seat_class: str,
    number_of_bags: int,
) -> BaggageCalculationOut | ErrorResponse:
    """Calculate baggage fee based on passenger seat class and loyalty tier status."""
    if number_of_bags < 0:
        return ErrorResponse(
            error="Number of bags cannot be negative",
            error_code="INVALID_BAG_COUNT",
            details=f"Received: {number_of_bags}",
        )

    # Determine user's loyalty tier if enrolled
    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    tier = account.tier if account else LoyaltyTier.STANDARD.value

    # Allowance is maximum of class allowance and tier allowance
    class_allowance = CLASS_FREE_BAGS.get(seat_class.lower(), 1)
    tier_allowance = TIER_FREE_BAGS.get(tier, 1)
    free_bags = max(class_allowance, tier_allowance)

    charged_bags = max(0, number_of_bags - free_bags)
    baggage_fee = charged_bags * EXCESS_BAG_FEE

    return BaggageCalculationOut(
        user_id=user_id,
        tier=tier,
        seat_class=seat_class,
        free_bags_allowed=free_bags,
        charged_bags=charged_bags,
        baggage_fee=baggage_fee,
    )
