from typing import Dict, Any, Optional, List, cast
import requests

from .exceptions import SeatDataException, AuthenticationError, RateLimitError


class SeatDataClient:
    BASE_URL = "https://seatdata.io/api"

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key or len(api_key) != 64:
            raise ValueError("API key must be a 64-character hexadecimal string")

        self._api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"api-key": api_key, "User-Agent": "SeatData-Python-SDK/0.1.0"})

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

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
