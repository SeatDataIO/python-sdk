import httpx
import pytest
import respx

from seatdata import SeatDataClient


@respx.mock
def test_get_account_returns_typed_response():
    payload = {
        "user_id": 4823,
        "email": "client@example.com",
        "company": "Acme Trading",
        "plans": [
            {
                "id": "professional",
                "name": "Professional",
                "status": "active",
                "billing_period_start": "2026-04-01T00:00:00Z",
                "billing_period_end": "2026-05-01T00:00:00Z",
                "renews_at": "2026-05-01T00:00:00Z",
            }
        ],
        "rate_limits": {
            "account": {"limit": 60, "window_seconds": 60},
            "events_search": {"limit": 6, "window_seconds": 60},
        },
    }
    route = respx.get("https://seatdata.io/api/v1/account").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_account()
    assert result["user_id"] == 4823
    assert result["plans"][0]["status"] == "active"
    assert result["rate_limits"]["events_search"]["limit"] == 6
    assert route.called


@respx.mock
def test_get_usage_returns_typed_response():
    payload = {
        "period_start": "2026-03-31T00:00:00Z",
        "period_end": "2026-04-30T00:00:00Z",
        "totals": {
            "api_calls": 4287,
            "events_searched": 3886,
            "salesdata_pulls": 312,
            "listings_pulls": 89,
            "stats_pulls": 0,
            "daily_csv_downloads": 0,
        },
        "by_endpoint": [{"endpoint": "events.search", "count": 3886}],
    }
    respx.get("https://seatdata.io/api/v1/usage").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_usage()
    assert result["totals"]["api_calls"] == 4287
