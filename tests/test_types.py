from seatdata.types import (
    AccountResponse,
    Plan,
    RateLimitInfo,
    UsageResponse,
    UsageTotals,
    UsageByEndpoint,
    EventSearchItem,
    EventSearchPage,
    EventStatsZone,
    EventStatsSnapshot,
    EventStatsPage,
    ErrorEnvelope,
    ErrorEnvelopeBody,
)


def test_account_response_is_dict_compatible():
    plan: Plan = {
        "id": "professional",
        "name": "Professional",
        "status": "active",
        "billing_period_start": "2026-04-01T00:00:00Z",
        "billing_period_end": "2026-05-01T00:00:00Z",
        "renews_at": "2026-05-01T00:00:00Z",
    }
    rate_limit: RateLimitInfo = {"limit": 60, "window_seconds": 60}
    account: AccountResponse = {
        "user_id": 4823,
        "email": "client@example.com",
        "plans": [plan],
        "rate_limits": {"account": rate_limit},
    }
    assert account["user_id"] == 4823
    assert account["plans"][0]["status"] == "active"


def test_usage_response_shape():
    totals: UsageTotals = {
        "api_calls": 4287,
        "events_searched": 3886,
        "salesdata_pulls": 312,
        "listings_pulls": 89,
        "stats_pulls": 0,
        "daily_csv_downloads": 0,
    }
    by_endpoint: UsageByEndpoint = {"endpoint": "events.search", "count": 3886}
    usage: UsageResponse = {
        "period_start": "2026-03-31T00:00:00Z",
        "period_end": "2026-04-30T00:00:00Z",
        "totals": totals,
        "by_endpoint": [by_endpoint],
    }
    assert usage["totals"]["api_calls"] == 4287


def test_event_search_item_minimal():
    item: EventSearchItem = {
        "event_id": 12345,
        "event_name": "Test",
        "event_date": "2026-06-15",
        "days_on_seatdata": 47,
        "first_seen_date": "2026-03-11",
        "venue_name": "MetLife",
        "venue_city": "East Rutherford",
        "venue_state": "NJ",
    }
    assert item["event_id"] == 12345


def test_event_stats_snapshot_with_zones():
    zone: EventStatsZone = {
        "zone_name": "Lower Bowl",
        "avg_price": 412.75,
        "median_price": 395.0,
        "get_in": 285.0,
        "get_in_qty2plus": 320.0,
    }
    snapshot: EventStatsSnapshot = {
        "timestamp": "2026-04-26T14:30:00Z",
        "total_listings_all": 487,
        "total_listings_active": 312,
        "listing_fill_rate": 0.64,
        "avg_price": 245.5,
        "median_price": 198.0,
        "get_in": 89.0,
        "get_in_qty2plus": 145.0,
        "zones": [zone],
    }
    assert snapshot["zones"][0]["zone_name"] == "Lower Bowl"


def test_event_stats_page_first_page_has_extra_fields():
    page: EventStatsPage = {
        "event_id": 12345,
        "data": [],
        "has_more": False,
        "next_cursor": None,
        "available_zones": ["Lower Bowl"],
        "total_count": 487,
    }
    assert page["available_zones"] == ["Lower Bowl"]


def test_error_envelope_shape():
    body: ErrorEnvelopeBody = {
        "type": "invalid_request",
        "code": "missing_parameter",
        "message": "event_id is required",
        "param": "event_id",
    }
    env: ErrorEnvelope = {"error": body}
    assert env["error"]["type"] == "invalid_request"


from datetime import datetime, timezone
from seatdata.types import parse_timestamp


def test_parse_timestamp_z_suffix():
    result = parse_timestamp("2026-04-26T14:30:00Z")
    assert result == datetime(2026, 4, 26, 14, 30, 0, tzinfo=timezone.utc)


def test_parse_timestamp_with_microseconds():
    result = parse_timestamp("2026-04-26T14:30:00.123456Z")
    assert result.microsecond == 123456
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_explicit_offset_passes_through():
    result = parse_timestamp("2026-04-26T14:30:00+00:00")
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_invalid_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_timestamp("not a timestamp")
