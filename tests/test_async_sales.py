import httpx
import pytest
import respx

from seatdata import AsyncSeatDataClient
from seatdata.exceptions import CursorExpiredError

API_KEY = "a" * 64
BASE = "https://seatdata.io"


def _page(data, has_more=False, next_cursor=None, first=True):
    body = {
        "event_id": 225220,
        "data": data,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }
    if first:
        body["total_count"] = 2
        body["sources"] = [
            {
                "source": "sh",
                "collecting_since": "2024-03-01",
                "tracked_for_event": True,
                "status": "ok",
            },
            {
                "source": "vs",
                "collecting_since": None,
                "tracked_for_event": False,
                "status": "ok",
            },
        ]
    return body


SH_ROW = {
    "source": "sh",
    "listing_id": 1,
    "all_in_price": None,
    "timestamp": 1757000000,
    "quantity": 2,
    "price": 145.0,
    "zone": "Lower Bowl",
    "section": "112",
    "row": "F",
}


@pytest.mark.asyncio
@respx.mock
async def test_get_event_sales_uses_internal_id_without_id_type():
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        page = await client.get_event_sales(event_id=225220)
    assert page["total_count"] == 2
    assert "id_type" not in route.calls[0].request.url.params


@pytest.mark.asyncio
@respx.mock
async def test_get_event_sales_maps_event_id_sh_to_marketplace():
    route = respx.get(f"{BASE}/api/v1/events/105294241/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        await client.get_event_sales(event_id_sh=105294241)
    assert route.calls[0].request.url.params["id_type"] == "marketplace"


@pytest.mark.asyncio
@respx.mock
async def test_source_is_omitted_when_not_supplied():
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        await client.get_event_sales(event_id=225220)
    assert "source" not in route.calls[0].request.url.params


@pytest.mark.asyncio
@respx.mock
async def test_iter_event_sales_resends_source_and_limit_on_every_page():
    pages = [
        _page([SH_ROW], has_more=True, next_cursor="c1"),
        _page([SH_ROW], has_more=False, next_cursor=None, first=False),
    ]
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        side_effect=[httpx.Response(200, json=p) for p in pages]
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        it = client.iter_event_sales(event_id=225220, source="all", limit=50)
        rows = [row async for row in it]
    assert len(rows) == 2
    assert len(route.calls) == 2
    for call in route.calls:
        assert call.request.url.params["source"] == "all"
        assert call.request.url.params["limit"] == "50"
    assert route.calls[1].request.url.params["starting_after"] == "c1"
    assert it.first_page["total_count"] == 2
    assert it.first_page["sources"][0]["source"] == "sh"


@pytest.mark.asyncio
@respx.mock
async def test_cursor_rejected_under_a_different_source_raises_cursor_expired():
    respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request",
                    "code": "invalid_cursor",
                    "message": "Cursor was issued under a different source.",
                    "param": "starting_after",
                }
            },
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(CursorExpiredError):
            await client.get_event_sales(event_id=225220, starting_after="c1", source="vs")


@pytest.mark.asyncio
@respx.mock
async def test_missing_and_conflicting_ids_raise_before_any_request():
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(ValueError):
            await client.get_event_sales()
        with pytest.raises(ValueError):
            await client.get_event_sales(event_id=1, event_id_sh=2)


@pytest.mark.asyncio
@respx.mock
async def test_iter_event_sales_resends_id_type_on_every_page():
    pages = [
        _page([SH_ROW], has_more=True, next_cursor="c1"),
        _page([SH_ROW], has_more=False, next_cursor=None, first=False),
    ]
    route = respx.get(f"{BASE}/api/v1/events/105294241/sales").mock(
        side_effect=[httpx.Response(200, json=p) for p in pages]
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        rows = [row async for row in client.iter_event_sales(event_id_sh=105294241, source="vs")]
    assert len(rows) == 2
    assert len(route.calls) == 2
    for call in route.calls:
        assert call.request.url.params["id_type"] == "marketplace"
        assert call.request.url.params["source"] == "vs"
    assert route.calls[1].request.url.params["starting_after"] == "c1"
