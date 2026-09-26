from typing import Literal

from pydantic import BaseModel, ConfigDict

# Seat class type definition
SeatClass = Literal['economy', 'business', 'galaxium']


class FlightQueryParams(BaseModel):
    """Query parameters for filtering and sorting flights."""
    # Location filters (case-insensitive partial match)
    origin: str | None = None
    destination: str | None = None
    
    # Date range filters (format: YYYY-MM-DD)
    departure_date_from: str | None = None
    departure_date_to: str | None = None
    
    # Price range filters
    min_price: int | None = None
    max_price: int | None = None
    
    # Seat availability filters (at least 1 seat available)
    has_economy: bool | None = None
    has_business: bool | None = None
    has_galaxium: bool | None = None
    
    # Sorting
    sort: Literal['price', 'departure_time', 'duration'] | None = None
    order: Literal['asc', 'desc'] | None = 'asc'


class FlightOut(BaseModel):
    flight_id: int
    origin: str
    destination: str
    departure_time: str  # Format: YYYY-MM-DD HH:MM
    arrival_time: str    # Format: YYYY-MM-DD HH:MM
    base_price: int  # Economy price (1x)
    economy_seats_available: int
    business_seats_available: int
    galaxium_seats_available: int
    # Computed prices for all classes
    economy_price: int
    business_price: int
    galaxium_price: int

    model_config = ConfigDict(from_attributes=True)


class BookingRequest(BaseModel):
    user_id: int
    name: str
    flight_id: int
    seat_class: SeatClass = 'economy'  # Default to economy


class BookingOut(BaseModel):
    booking_id: int
    user_id: int
    flight_id: int
    status: str
    booking_time: str
    seat_class: str
    price_paid: int

    model_config = ConfigDict(from_attributes=True)


class UserRegistration(BaseModel):
    name: str
    email: str


class UserOut(BaseModel):
    user_id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str
    details: str | None = None


# Loyalty schemas
LoyaltyTierName = Literal['standard', 'silver', 'gold', 'starlight']


class LoyaltyEnrollRequest(BaseModel):
    user_id: int


class LoyaltyAccountOut(BaseModel):
    account_id: int
    user_id: int
    tier: str
    miles_balance: int
    lifetime_miles: int
    enrolled_at: str

    model_config = ConfigDict(from_attributes=True)


class LoyaltyTransactionOut(BaseModel):
    transaction_id: int
    user_id: int
    transaction_type: str
    miles: int
    description: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class MilesRedeemRequest(BaseModel):
    user_id: int
    miles: int
    description: str


class BaggageCalculationRequest(BaseModel):
    user_id: int
    seat_class: SeatClass
    number_of_bags: int


class BaggageCalculationOut(BaseModel):
    user_id: int
    tier: str
    seat_class: str
    free_bags_allowed: int
    charged_bags: int
    baggage_fee: int


class PerksSummaryOut(BaseModel):
    tier: str
    lounge_access: bool
    priority_boarding_group: str
    free_checked_bags: int
    discount_percentage: int


class SeatUpgradeRequest(BaseModel):
    user_id: int
    name: str
    target_class: Literal['business', 'galaxium']


class SeatUpgradeOut(BaseModel):
    booking_id: int
    user_id: int
    flight_id: int
    previous_class: str
    new_class: str
    miles_deducted: int
    status: str

