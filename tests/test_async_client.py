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
