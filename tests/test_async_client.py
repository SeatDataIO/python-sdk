import httpx
import pytest
import respx

from seatdata import AsyncSeatDataClient


class TestAsyncSeatDataClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_account(self):
        respx.get("https://seatdata.io/api/v1/account").mock(
            return_value=httpx.Response(
                200, json={"user_id": 1, "email": "x", "plans": [], "rate_limits": {}}
            )
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_account()
            assert result["user_id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_events(self):
        respx.get("https://seatdata.io/api/v1/events/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "event_id": 1,
                            "event_name": "X",
                            "event_date": "2026-06-15",
                            "days_on_seatdata": 1,
                            "first_seen_date": "2026-06-14",
                            "venue_name": "V",
                            "venue_city": "C",
                            "venue_state": "NJ",
                        }
                    ],
                    "has_more": False,
                    "next_cursor": None,
                },
            )
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            items = await client.search_events(event_name="X")
            assert items[0]["event_id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_iter_search_events(self):
        respx.get("https://seatdata.io/api/v1/events/search").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "event_id": 1,
                                "event_name": "X",
                                "event_date": "2026-06-15",
                                "days_on_seatdata": 1,
                                "first_seen_date": "2026-06-14",
                                "venue_name": "V",
                                "venue_city": "C",
                                "venue_state": "NJ",
                            }
                        ],
                        "has_more": True,
                        "next_cursor": "c1",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "event_id": 2,
                                "event_name": "Y",
                                "event_date": "2026-06-16",
                                "days_on_seatdata": 1,
                                "first_seen_date": "2026-06-15",
                                "venue_name": "V",
                                "venue_city": "C",
                                "venue_state": "NJ",
                            }
                        ],
                        "has_more": False,
                        "next_cursor": None,
                    },
                ),
            ]
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            ids = []
            async for item in client.iter_search_events():
                ids.append(item["event_id"])
        assert ids == [1, 2]

    @pytest.mark.asyncio
    @respx.mock
    async def test_iter_event_stats(self):
        url = "https://seatdata.io/api/v1/events/12345/stats"
        respx.get(url).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "event_id": 12345,
                        "data": [
                            {
                                "timestamp": "2026-04-26T14:30:00Z",
                                "total_listings_all": 1,
                                "total_listings_active": 1,
                                "listing_fill_rate": 1.0,
                                "avg_price": 1,
                                "median_price": 1,
                                "get_in": 1,
                                "get_in_qty2plus": 1,
                                "zones": [],
                            }
                        ],
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
                        "data": [
                            {
                                "timestamp": "2026-04-26T15:00:00Z",
                                "total_listings_all": 1,
                                "total_listings_active": 1,
                                "listing_fill_rate": 1.0,
                                "avg_price": 1,
                                "median_price": 1,
                                "get_in": 1,
                                "get_in_qty2plus": 1,
                                "zones": [],
                            }
                        ],
                        "has_more": False,
                        "next_cursor": None,
                    },
                ),
            ]
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            timestamps = [s["timestamp"] async for s in client.iter_event_stats(12345)]
        assert timestamps == ["2026-04-26T14:30:00Z", "2026-04-26T15:00:00Z"]

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises(self):
        with pytest.raises(ValueError, match="API key must be a 64-character hexadecimal string"):
            AsyncSeatDataClient(api_key="short")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_usage(self):
        payload = {
            "period_start": "2026-03-31T00:00:00Z",
            "period_end": "2026-04-30T00:00:00Z",
            "totals": {
                "api_calls": 1,
                "events_searched": 1,
                "salesdata_pulls": 0,
                "listings_pulls": 0,
                "stats_pulls": 0,
                "daily_csv_downloads": 0,
            },
            "by_endpoint": [],
        }
        respx.get("https://seatdata.io/api/v1/usage").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_usage()
            assert result["totals"]["api_calls"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_event_stats(self):
        payload = {
            "event_id": 12345,
            "data": [],
            "has_more": False,
            "next_cursor": None,
            "available_zones": [],
            "total_count": 0,
        }
        respx.get("https://seatdata.io/api/v1/events/12345/stats").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_event_stats(12345)
            assert result["event_id"] == 12345
            assert result["total_count"] == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_sales_data(self):
        respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
            return_value=httpx.Response(200, json=[{"price": 100}])
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_sales_data(event_id="123")
            assert result == [{"price": 100}]

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_listings(self):
        respx.get("https://seatdata.io/api/v0.1/listings/get").mock(
            return_value=httpx.Response(200, json={"listings": []})
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_listings(event_id="123")
            assert result == {"listings": []}

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_daily_csv(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(200, text="a,b\n1,2")
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.download_daily_csv()
            assert result == "a,b\n1,2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_event_request(self):
        respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
            return_value=httpx.Response(202, json={"job_id": "x"})
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.create_event_request(search_query="X")
            assert result == {"job_id": "x"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_event_request_add_async_alias_emits_deprecation(self):
        import warnings

        respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
            return_value=httpx.Response(202, json={"job_id": "x"})
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                await client.event_request_add(search_query="X")
            assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    @pytest.mark.asyncio
    async def test_aclose_closes_underlying_async_client(self):
        client = AsyncSeatDataClient(api_key="a" * 64)
        client._transport._ensure_async_client()
        assert client._transport._async_client is not None
        assert not client._transport._async_client.is_closed
        await client.aclose()
        assert client._transport._async_client is None
