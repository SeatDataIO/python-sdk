import httpx
import pytest
import respx

from seatdata import SeatDataClient
from seatdata.exceptions import CursorExpiredError


def stats_url(event_id):
    return f"https://seatdata.io/api/v1/events/{event_id}/stats"


def make_snapshot(timestamp="2026-04-26T14:30:00Z"):
    return {
        "timestamp": timestamp,
        "total_listings_all": 487,
        "total_listings_active": 312,
        "listing_fill_rate": 0.64,
        "avg_price": 245.5,
        "median_price": 198.0,
        "get_in": 89.0,
        "get_in_qty2plus": 145.0,
        "zones": [],
    }


@respx.mock
def test_get_event_stats_first_page_includes_zones_and_total():
    payload = {
        "event_id": 12345,
        "data": [make_snapshot()],
        "has_more": False,
        "next_cursor": None,
        "available_zones": ["Lower Bowl", "Upper Deck"],
        "total_count": 1,
    }
    respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_event_stats(12345)
    assert result["available_zones"] == ["Lower Bowl", "Upper Deck"]
    assert result["total_count"] == 1
    assert result["data"][0]["timestamp"] == "2026-04-26T14:30:00Z"


@respx.mock
def test_get_event_stats_with_cursor_continuation():
    payload = {
        "event_id": 12345,
        "data": [make_snapshot()],
        "has_more": False,
        "next_cursor": None,
    }
    route = respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    client.get_event_stats(12345, starting_after="cursor1", limit=50)
    params = route.calls.last.request.url.params
    assert params["starting_after"] == "cursor1"
    assert params["limit"] == "50"


@respx.mock
def test_get_event_stats_with_date_filters():
    payload = {"event_id": 12345, "data": [], "has_more": False, "next_cursor": None}
    route = respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    client.get_event_stats(12345, start_date="2026-04-01", end_date="2026-04-30")
    params = route.calls.last.request.url.params
    assert params["start_date"] == "2026-04-01"
    assert params["end_date"] == "2026-04-30"


@respx.mock
def test_iter_event_stats_walks_pages():
    respx.get(stats_url(12345)).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "event_id": 12345,
                    "data": [make_snapshot("2026-04-26T14:30:00Z")],
                    "has_more": True,
                    "next_cursor": "c1",
                    "available_zones": [],
                    "total_count": 2,
                },
            ),
            httpx.Response(
                200,
                json={
                    "event_id": 12345,
                    "data": [make_snapshot("2026-04-26T15:00:00Z")],
                    "has_more": False,
                    "next_cursor": None,
                },
            ),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    timestamps = [s["timestamp"] for s in client.iter_event_stats(12345)]
    assert timestamps == ["2026-04-26T14:30:00Z", "2026-04-26T15:00:00Z"]


@respx.mock
def test_iter_event_stats_raises_cursor_expired_with_progress():
    respx.get(stats_url(12345)).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "event_id": 12345,
                    "data": [make_snapshot()],
                    "has_more": True,
                    "next_cursor": "expired_cursor",
                },
            ),
            httpx.Response(
                400,
                json={
                    "error": {
                        "type": "invalid_request",
                        "code": "invalid_cursor",
                        "message": "cursor expired",
                    }
                },
            ),
        ]
    )
    client = SeatDataClient(api_key="a" * 64, max_retries=0)
    it = client.iter_event_stats(12345)
    next(it)
    with pytest.raises(CursorExpiredError) as exc_info:
        next(it)
    assert exc_info.value.items_yielded == 1
    assert exc_info.value.last_cursor == "expired_cursor"
