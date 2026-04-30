import json

import pytest
import respx
import httpx

from seatdata import (
    SeatDataClient,
    SeatDataException,
    AuthenticationError,
    RateLimitError,
    SubscriptionError,
    NotFoundError,
    ServiceUnavailableError,
)


class TestSeatDataClient:

    def test_init_valid_api_key(self):
        api_key = "a" * 64
        client = SeatDataClient(api_key=api_key)
        assert client._api_key == api_key
        assert client.timeout == 30

    def test_init_invalid_api_key_length(self):
        with pytest.raises(ValueError, match="API key must be a 64-character hexadecimal string"):
            SeatDataClient(api_key="short_key")

    def test_init_empty_api_key(self):
        with pytest.raises(ValueError, match="API key must be a 64-character hexadecimal string"):
            SeatDataClient(api_key="")

    @respx.mock
    def test_authentication_error(self):
        respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
            return_value=httpx.Response(401)
        )
        client = SeatDataClient(api_key="a" * 64)
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            client.get_sales_data(event_id="test_event")

    @respx.mock
    def test_rate_limit_error(self):
        respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
            return_value=httpx.Response(429)
        )
        client = SeatDataClient(api_key="a" * 64)
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            client.search_events(event_name="test")

    @respx.mock
    def test_bad_request_error(self):
        respx.get("https://seatdata.io/api/v0.1/listings/get").mock(
            return_value=httpx.Response(400, text="Missing required parameter")
        )
        client = SeatDataClient(api_key="a" * 64)
        with pytest.raises(SeatDataException, match="Bad request: Missing required parameter"):
            client.get_listings(event_id="test")

    @respx.mock
    def test_get_sales_data_success(self):
        test_data = {"sales": [{"price": 100, "quantity": 2}]}
        route = respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
            return_value=httpx.Response(200, json=test_data)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.get_sales_data(event_id="test_event")
        assert result == test_data
        assert route.called

    @respx.mock
    def test_get_listings_success(self):
        test_data = {"listings": [{"id": "123", "price": 50}]}
        respx.get("https://seatdata.io/api/v0.1/listings/get").mock(
            return_value=httpx.Response(200, json=test_data)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.get_listings(event_id_sh="test_sh_id")
        assert result == test_data

    def test_get_sales_data_missing_params(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="Either event_id or event_id_sh must be provided"):
            client.get_sales_data()

    def test_get_listings_missing_params(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="Either event_id or event_id_sh must be provided"):
            client.get_listings()

    @respx.mock
    def test_search_events_success(self):
        test_data = [{"event_name": "Concert", "venue": "Stadium"}]
        route = respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
            return_value=httpx.Response(200, json=test_data)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.search_events(event_name="Concert", venue_name="Stadium")
        assert result == test_data
        body = json.loads(route.calls.last.request.content)
        assert body == {"event_name": "Concert", "venue_name": "Stadium"}

    def test_context_manager(self):
        with SeatDataClient(api_key="a" * 64) as client:
            assert client._api_key == "a" * 64

    @respx.mock
    def test_event_request_add_success(self):
        test_data = {"job_id": "test-job-123", "status": "pending"}
        route = respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
            return_value=httpx.Response(202, json=test_data)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.event_request_add(search_query="Taylor Swift Concert")
        assert result == test_data
        body = json.loads(route.calls.last.request.content)
        assert body == {"search_query": "Taylor Swift Concert"}

    def test_event_request_add_empty_query(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="search_query must be provided"):
            client.event_request_add(search_query="")

    @respx.mock
    def test_event_request_status_success(self):
        test_data = {
            "job_id": "test-job-123",
            "status": "completed",
            "result": {"event_id": "ev123"},
        }
        route = respx.get(
            "https://seatdata.io/api/v0.4/events/event-request-status/test-job-123/"
        ).mock(return_value=httpx.Response(200, json=test_data))
        client = SeatDataClient(api_key="a" * 64)
        result = client.event_request_status(job_id="test-job-123")
        assert result == test_data
        assert route.called

    def test_event_request_status_empty_job_id(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="job_id must be provided"):
            client.event_request_status(job_id="")

    @respx.mock
    def test_event_request_status_not_found(self):
        respx.get(
            "https://seatdata.io/api/v0.4/events/event-request-status/invalid-job-id/"
        ).mock(return_value=httpx.Response(404, text="Job not found"))
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Not found: Job not found"):
            client.event_request_status(job_id="invalid-job-id")

    @respx.mock
    def test_download_daily_csv_success(self):
        csv_content = "event_id,event_name,venue\n123,Concert,Stadium\n456,Game,Arena"
        route = respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(200, text=csv_content)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.download_daily_csv()
        assert result == csv_content
        assert route.called

    @respx.mock
    def test_download_daily_csv_with_date(self):
        csv_content = "event_id,event_name\n123,Concert"
        route = respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(200, text=csv_content)
        )
        client = SeatDataClient(api_key="a" * 64)
        result = client.download_daily_csv(date="20251225")
        assert result == csv_content
        assert route.calls.last.request.url.params["date"] == "20251225"

    @respx.mock
    def test_download_daily_csv_authentication_error(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            client.download_daily_csv()

    @respx.mock
    def test_download_daily_csv_api_subscription_error(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(401, json={"error": "API subscription required"})
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SubscriptionError, match="API subscription required"):
            client.download_daily_csv()

    @respx.mock
    def test_download_daily_csv_csv_subscription_error(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(
                401, json={"error": "Daily Event CSV subscription required"}
            )
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SubscriptionError, match="Daily Event CSV subscription required"):
            client.download_daily_csv()

    @respx.mock
    def test_download_daily_csv_not_found(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(
                404, json={"error": "CSV file not found for requested date"}
            )
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(NotFoundError, match="CSV file not found for requested date"):
            client.download_daily_csv(date="20251201")

    @respx.mock
    def test_download_daily_csv_rate_limit(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(
                429, json={"error": "Too many requests", "retry_after": 3600}
            )
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(RateLimitError, match="Too many requests"):
            client.download_daily_csv()

    @respx.mock
    def test_download_daily_csv_service_unavailable(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(503, json={"error": "Service temporarily unavailable"})
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ServiceUnavailableError, match="Service temporarily unavailable"):
            client.download_daily_csv()

    @respx.mock
    def test_download_daily_csv_bad_request_invalid_date_format(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(400, text="Invalid date format. Use YYYYMMDD.")
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Invalid date format"):
            client.download_daily_csv(date="2025-12-25")

    @respx.mock
    def test_download_daily_csv_bad_request_future_date(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(400, text="Cannot request future dates.")
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Cannot request future dates"):
            client.download_daily_csv(date="20991231")

    @respx.mock
    def test_download_daily_csv_bad_request_old_date(self):
        respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
            return_value=httpx.Response(400, text="Cannot request dates older than 30 days.")
        )
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Cannot request dates older than 30 days"):
            client.download_daily_csv(date="20200101")
