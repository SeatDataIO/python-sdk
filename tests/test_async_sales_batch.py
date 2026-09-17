import httpx
import pytest
import respx

from seatdata import AsyncSeatDataClient, SeatDataPaymentError, SeatDataRateLimitError

API_KEY = "a" * 64
BASE = "https://seatdata.io"
PATH = f"{BASE}/api/v1/events/sales/batch"

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
async def test_batch_posts_payload_and_returns_three_keys():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {"105294241": [SH_ROW]},
                "errors": {"225220": "not_found"},
                "sources": {"105294241": []},
            },
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        result = await client.get_event_sales_batch(event_ids_sh=[105294241], event_ids=[225220])
    assert set(result) == {"results", "errors", "sources"}
    assert result["errors"]["225220"] == "not_found"
    import json as _json

    body = _json.loads(route.calls[0].request.content)
    assert body == {"event_ids_sh": [105294241], "event_ids": [225220]}


@pytest.mark.asyncio
@respx.mock
async def test_digit_string_ids_look_up_by_decimal_string():
    respx.post(PATH).mock(
        return_value=httpx.Response(
            200, json={"results": {"105294241": [SH_ROW]}, "errors": {}, "sources": {}}
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        result = await client.get_event_sales_batch(event_ids_sh=["105294241"])
    assert result["results"]["105294241"] == [SH_ROW]


@pytest.mark.asyncio
@respx.mock
async def test_same_numeric_id_in_both_lists_is_sent_twice():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(200, json={"results": {}, "errors": {}, "sources": {}})
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        await client.get_event_sales_batch(event_ids_sh=[7], event_ids=[7])
    import json as _json

    body = _json.loads(route.calls[0].request.content)
    assert body == {"event_ids_sh": [7], "event_ids": [7]}


@pytest.mark.asyncio
@respx.mock
async def test_source_goes_on_the_query_string_not_the_body():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(200, json={"results": {}, "errors": {}, "sources": {}})
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        await client.get_event_sales_batch(event_ids_sh=[1], source="all")
    import json as _json

    assert route.calls[0].request.url.params["source"] == "all"
    assert "source" not in _json.loads(route.calls[0].request.content)


@pytest.mark.asyncio
@respx.mock
async def test_per_event_payment_required_is_data_not_an_exception():
    respx.post(PATH).mock(
        return_value=httpx.Response(
            200, json={"results": {}, "errors": {"7": "payment_required"}, "sources": {}}
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        result = await client.get_event_sales_batch(event_ids_sh=[7])
    assert result["errors"]["7"] == "payment_required"


@pytest.mark.asyncio
@respx.mock
async def test_raw_402_raises_payment_error():
    respx.post(PATH).mock(
        return_value=httpx.Response(
            402,
            json={
                "error": {
                    "type": "payment_required",
                    "code": "balance_exhausted",
                    "message": "no funds",
                }
            },
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(SeatDataPaymentError):
            await client.get_event_sales_batch(event_ids_sh=[7])


@pytest.mark.asyncio
@respx.mock
async def test_batch_is_not_retried_on_429():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {
                    "type": "rate_limit_error",
                    "code": "rate_limited",
                    "message": "slow down",
                }
            },
        )
    )
    async with AsyncSeatDataClient(api_key=API_KEY, max_retries=3) as client:
        with pytest.raises(SeatDataRateLimitError):
            await client.get_event_sales_batch(event_ids_sh=[7])
    assert len(route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_cap_and_empty_payload_raise_before_any_request():
    async with AsyncSeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(ValueError):
            await client.get_event_sales_batch()
        with pytest.raises(ValueError):
            await client.get_event_sales_batch(event_ids_sh=list(range(101)))
