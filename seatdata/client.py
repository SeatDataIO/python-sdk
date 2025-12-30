from typing import Dict, Any, Optional, List, cast
import requests

from .exceptions import (
    SeatDataException,
    AuthenticationError,
    RateLimitError,
    SubscriptionError,
    NotFoundError,
    ServiceUnavailableError,
)


class SeatDataClient:
    BASE_URL = "https://seatdata.io/api"

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key or len(api_key) != 64:
            raise ValueError("API key must be a 64-character hexadecimal string")

        self._api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"api-key": api_key, "User-Agent": "SeatData-Python-SDK/0.3.0"})

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = self.BASE_URL + endpoint

        try:
            response = self.session.request(
                method=method, url=url, params=params, json=json_data, timeout=self.timeout
            )

            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 400:
                raise SeatDataException(f"Bad request: {response.text}")
            elif response.status_code == 404:
                raise SeatDataException(f"Not found: {response.text}")

            if response.status_code not in [200, 202]:
                response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            raise SeatDataException(f"Request failed: {str(e)}")

    def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")

        params = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh

        return cast(
            List[Dict[str, Any]], self._make_request("GET", "/v0.3/salesdata/get", params=params)
        )

    def get_listings(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> Dict[str, Any]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")

        params = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh

        return cast(Dict[str, Any], self._make_request("GET", "/v0.1/listings/get", params=params))

    def search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        return_full_response: bool = False,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        search_params = {}

        if event_name:
            search_params["event_name"] = event_name
        if event_date:
            search_params["event_date"] = event_date
        if venue_name:
            search_params["venue_name"] = venue_name
        if venue_city:
            search_params["venue_city"] = venue_city
        if venue_state:
            search_params["venue_state"] = venue_state

        search_params.update(kwargs)

        response = self._make_request("POST", "/v0.3.1/events/search", json_data=search_params)

        if return_full_response:
            return cast(List[Dict[str, Any]], response)

        if isinstance(response, dict) and "items" in response:
            return cast(List[Dict[str, Any]], response["items"])

        return cast(List[Dict[str, Any]], response)

    def event_request_add(self, search_query: str) -> Dict[str, Any]:
        if not search_query:
            raise ValueError("search_query must be provided")

        data = {"search_query": search_query}

        response = self._make_request("POST", "/v0.4/events/event-request-add", json_data=data)

        if response is None:
            raise SeatDataException("Empty response from API")

        return cast(Dict[str, Any], response)

    def event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")

        endpoint = f"/v0.4/events/event-request-status/{job_id}/"

        response = self._make_request("GET", endpoint)

        if response is None:
            raise SeatDataException("Empty response from API")

        return cast(Dict[str, Any], response)

    def download_daily_csv(self, date: Optional[str] = None) -> str:
        url = self.BASE_URL + "/v0.5/daily-csv/download"
        params = {}
        if date:
            params["date"] = date

        try:
            response = self.session.request(
                method="GET", url=url, params=params, timeout=self.timeout
            )

            if response.status_code == 200:
                return response.text

            if response.status_code == 400:
                raise SeatDataException(f"Bad request: {response.text}")
            elif response.status_code == 401:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", "")
                    if "subscription" in error_msg.lower():
                        raise SubscriptionError(error_msg)
                except (ValueError, KeyError):
                    pass
                raise AuthenticationError("Invalid API key")
            elif response.status_code == 404:
                try:
                    error_data = response.json()
                    raise NotFoundError(error_data.get("error", "CSV file not found"))
                except ValueError:
                    raise NotFoundError("CSV file not found")
            elif response.status_code == 429:
                try:
                    error_data = response.json()
                    retry_after = error_data.get("retry_after", "")
                    raise RateLimitError(
                        f"{error_data.get('error', 'Rate limit exceeded')}"
                        + (f" (retry after {retry_after}s)" if retry_after else "")
                    )
                except ValueError:
                    raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 503:
                try:
                    error_data = response.json()
                    raise ServiceUnavailableError(
                        error_data.get("error", "Service temporarily unavailable")
                    )
                except ValueError:
                    raise ServiceUnavailableError("Service temporarily unavailable")

            response.raise_for_status()
            return response.text

        except requests.exceptions.RequestException as e:
            raise SeatDataException(f"Request failed: {str(e)}")

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
