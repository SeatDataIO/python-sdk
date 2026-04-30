import json
import warnings

import httpx
import pytest
import respx

from seatdata import SeatDataClient


@respx.mock
def test_search_events_legacy_calls_v031_post():
    route = respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
        return_value=httpx.Response(200, json={"items": [{"event_id": 1}]})
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = client.search_events_legacy(event_name="Taylor")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"event_name": "Taylor"}
    assert any(
        issubclass(w.category, DeprecationWarning) and "search_events" in str(w.message)
        for w in caught
    )
    assert result == [{"event_id": 1}]


@respx.mock
def test_search_events_legacy_return_full_response():
    payload = {"result_total": 1, "items": [{"event_id": 1}]}
    respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = client.search_events_legacy(event_name="X", return_full_response=True)
    assert result == payload
