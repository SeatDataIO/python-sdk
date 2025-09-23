import pytest
from unittest.mock import Mock, patch

from seatdata import SeatDataClient, SeatDataException, AuthenticationError, RateLimitError


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

    @patch("seatdata.client.requests.Session")
    def test_authentication_error(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            client.get_sales_data(event_id="test_event")

    @patch("seatdata.client.requests.Session")
    def test_rate_limit_error(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 429
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            client.search_events(event_name="test")

    @patch("seatdata.client.requests.Session")
    def test_bad_request_error(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Missing required parameter"
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Bad request: Missing required parameter"):
            client.get_listings(event_id="test")

    @patch("seatdata.client.requests.Session")
    def test_get_sales_data_success(self, mock_session):
        test_data = {"sales": [{"price": 100, "quantity": 2}]}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = test_data
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)
        result = client.get_sales_data(event_id="test_event")

        assert result == test_data
        mock_session.return_value.request.assert_called_once()

    @patch("seatdata.client.requests.Session")
    def test_get_listings_success(self, mock_session):
        test_data = {"listings": [{"id": "123", "price": 50}]}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = test_data
        mock_session.return_value.request.return_value = mock_response

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

    @patch("seatdata.client.requests.Session")
    def test_search_events_success(self, mock_session):
        test_data = [{"event_name": "Concert", "venue": "Stadium"}]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = test_data
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)
        result = client.search_events(event_name="Concert", venue_name="Stadium")

        assert result == test_data

        call_args = mock_session.return_value.request.call_args
        assert call_args.kwargs["json"] == {"event_name": "Concert", "venue_name": "Stadium"}

    @patch("seatdata.client.requests.Session")
    def test_context_manager(self, mock_session):
        mock_close = Mock()
        mock_session.return_value.close = mock_close

        with SeatDataClient(api_key="a" * 64) as client:
            assert client._api_key == "a" * 64

        mock_close.assert_called_once()

    @patch("seatdata.client.requests.Session")
    def test_event_request_add_success(self, mock_session):
        test_data = {"job_id": "test-job-123", "status": "pending"}

        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = test_data
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)
        result = client.event_request_add(search_query="Taylor Swift Concert")

        assert result == test_data
        call_args = mock_session.return_value.request.call_args
        assert call_args.kwargs["json"] == {"search_query": "Taylor Swift Concert"}

    def test_event_request_add_empty_query(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="search_query must be provided"):
            client.event_request_add(search_query="")

    @patch("seatdata.client.requests.Session")
    def test_event_request_status_success(self, mock_session):
        test_data = {
            "job_id": "test-job-123",
            "status": "completed",
            "result": {"event_id": "ev123"},
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = test_data
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)
        result = client.event_request_status(job_id="test-job-123")

        assert result == test_data
        call_args = mock_session.return_value.request.call_args
        assert "/v0.4/events/event-request-status/test-job-123/" in call_args.kwargs["url"]

    def test_event_request_status_empty_job_id(self):
        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(ValueError, match="job_id must be provided"):
            client.event_request_status(job_id="")

    @patch("seatdata.client.requests.Session")
    def test_event_request_status_not_found(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Job not found"
        mock_session.return_value.request.return_value = mock_response

        client = SeatDataClient(api_key="a" * 64)

        with pytest.raises(SeatDataException, match="Not found: Job not found"):
            client.event_request_status(job_id="invalid-job-id")
