from typing import Dict, List, Optional
from typing_extensions import NotRequired, TypedDict


class RateLimitInfo(TypedDict):
    limit: int
    window_seconds: int


class Plan(TypedDict):
    id: str
    name: str
    status: str
    billing_period_start: Optional[str]
    billing_period_end: Optional[str]
    renews_at: Optional[str]


class AccountResponse(TypedDict):
    user_id: int
    email: str
    company: NotRequired[str]
    plans: List[Plan]
    rate_limits: Dict[str, RateLimitInfo]


class UsageTotals(TypedDict):
    api_calls: int
    events_searched: int
    salesdata_pulls: int
    listings_pulls: int
    stats_pulls: int
    daily_csv_downloads: int


class UsageByEndpoint(TypedDict):
    endpoint: str
    count: int


class UsageResponse(TypedDict):
    period_start: str
    period_end: str
    totals: UsageTotals
    by_endpoint: List[UsageByEndpoint]


class EventSearchItem(TypedDict):
    event_id: int
    event_name: str
    event_date: str
    event_time: NotRequired[str]
    tm_event_id: NotRequired[Optional[str]]
    days_on_seatdata: int
    first_seen_date: str
    venue_name: str
    venue_city: str
    venue_state: str
    venue_country_code: NotRequired[Optional[str]]
    venue_country: NotRequired[Optional[str]]
    venue_lat: NotRequired[Optional[float]]
    venue_lng: NotRequired[Optional[float]]
    venue_slug: NotRequired[Optional[str]]
    venue_tm_id: NotRequired[Optional[str]]
    std_event_id: NotRequired[Optional[int]]
    std_venue_id: NotRequired[Optional[int]]
    performer: NotRequired[Optional[str]]
    event_type: NotRequired[Optional[str]]
    tour_name: NotRequired[Optional[str]]


class EventSearchPage(TypedDict):
    data: List[EventSearchItem]
    has_more: bool
    next_cursor: Optional[str]


class EventStatsZone(TypedDict):
    zone_name: str
    avg_price: float
    median_price: float
    get_in: float
    get_in_qty2plus: float


class EventStatsSnapshot(TypedDict):
    timestamp: str
    total_listings_all: int
    total_listings_active: int
    listing_fill_rate: float
    avg_price: float
    median_price: float
    get_in: float
    get_in_qty2plus: float
    zones: List[EventStatsZone]


class EventStatsPage(TypedDict):
    event_id: int
    data: List[EventStatsSnapshot]
    has_more: bool
    next_cursor: Optional[str]
    available_zones: NotRequired[List[str]]
    total_count: NotRequired[int]


class ErrorEnvelopeBody(TypedDict):
    type: str
    code: str
    message: str
    param: NotRequired[str]


class ErrorEnvelope(TypedDict):
    error: ErrorEnvelopeBody


from datetime import datetime


def parse_timestamp(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)
