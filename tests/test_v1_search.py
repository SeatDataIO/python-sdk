import httpx
import pytest
import respx

from seatdata import SeatDataClient

SEARCH_URL = "https://seatdata.io/api/v1/events/search"


def make_item(event_id, name="Test"):
    return {
        "event_id": event_id,
        "event_name": name,
        "event_date": "2026-06-15",
        "days_on_seatdata": 47,
        "first_seen_date": "2026-03-11",
        "venue_name": "MetLife",
        "venue_city": "East Rutherford",
        "venue_state": "NJ",
    }


@respx.mock
def test_search_events_returns_items_list():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [make_item(1), make_item(2)], "has_more": False, "next_cursor": None},
        )
    )
    client = SeatDataClient(api_key="a" * 64)
    items = client.search_events(event_name="Taylor")
    assert isinstance(items, list)
    assert items[0]["event_id"] == 1
    assert route.calls.last.request.url.params["event_name"] == "Taylor"


@respx.mock
def test_search_events_page_returns_envelope():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [make_item(1)], "has_more": True, "next_cursor": "c1"},
        )
    )
    client = SeatDataClient(api_key="a" * 64)
    page = client.search_events_page(event_name="Taylor")
    assert page["data"][0]["event_id"] == 1
    assert page["has_more"] is True
    assert page["next_cursor"] == "c1"


@respx.mock
def test_search_events_page_passes_starting_after():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "has_more": False, "next_cursor": None})
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events_page(starting_after="cursor1", limit=50)
    params = route.calls.last.request.url.params
    assert params["starting_after"] == "cursor1"
    assert params["limit"] == "50"


@respx.mock
def test_iter_search_events_walks_pages():
    respx.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": [make_item(1), make_item(2)], "has_more": True, "next_cursor": "c1"},
            ),
            httpx.Response(
                200, json={"data": [make_item(3)], "has_more": False, "next_cursor": None}
            ),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    ids = [item["event_id"] for item in client.iter_search_events(event_name="X")]
    assert ids == [1, 2, 3]


@respx.mock
def test_iter_search_events_exposes_current_cursor():
    respx.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(
                200, json={"data": [make_item(1)], "has_more": True, "next_cursor": "c1"}
            ),
            httpx.Response(
                200, json={"data": [make_item(2)], "has_more": False, "next_cursor": None}
            ),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    it = client.iter_search_events()
    next(it)
    next(it)
    assert it.current_cursor == "c1"


@respx.mock
def test_search_events_supports_all_documented_filters():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "has_more": False, "next_cursor": None})
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events(
        event_name="X",
        event_date="2026-06",
        venue_name="MetLife",
        venue_city="East Rutherford",
        venue_state="NJ",
        country_code="US",
        tm_event_id="abc",
        std_event_id=42,
        std_venue_id=7,
        venue_slug="metlife-stadium",
        historical=True,
        limit=100,
    )
    params = route.calls.last.request.url.params
    assert params["country_code"] == "US"
    assert params["std_event_id"] == "42"
    assert params["historical"] == "true"


@respx.mock
def test_search_events_omits_none_filters():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "has_more": False, "next_cursor": None})
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events(event_name="X")
    params = route.calls.last.request.url.params
    assert "venue_name" not in params
    assert "country_code" not in params
