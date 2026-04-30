from typing import Any, Dict, List, Optional, cast

from ._transport import _Transport
from .exceptions import SeatDataError
from .pagination import PageIterator
from .types import AccountResponse, EventSearchItem, EventSearchPage, UsageResponse


class SeatDataClient:
    BASE_URL = "https://seatdata.io"

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        base_url: Optional[str] = None,
    ) -> None:
        if not api_key or len(api_key) != 64:
            raise ValueError("API key must be a 64-character hexadecimal string")
        self._api_key = api_key
        self.timeout = timeout
        self._transport = _Transport(
            api_key=api_key,
            base_url=base_url or self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
        )

    def get_account(self) -> AccountResponse:
        return cast(AccountResponse, self._transport.request_json("GET", "/api/v1/account"))

    def get_usage(self) -> UsageResponse:
        return cast(UsageResponse, self._transport.request_json("GET", "/api/v1/usage"))

    def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            List[Dict[str, Any]],
            self._transport.request_json("GET", "/api/v0.3/salesdata/get", params=params),
        )

    def get_listings(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> Dict[str, Any]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            Dict[str, Any],
            self._transport.request_json("GET", "/api/v0.1/listings/get", params=params),
        )

    def _search_events_params(
        self,
        *,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if event_name is not None:
            params["event_name"] = event_name
        if event_date is not None:
            params["event_date"] = event_date
        if venue_name is not None:
            params["venue_name"] = venue_name
        if venue_city is not None:
            params["venue_city"] = venue_city
        if venue_state is not None:
            params["venue_state"] = venue_state
        if country_code is not None:
            params["country_code"] = country_code
        if tm_event_id is not None:
            params["tm_event_id"] = tm_event_id
        if std_event_id is not None:
            params["std_event_id"] = std_event_id
        if std_venue_id is not None:
            params["std_venue_id"] = std_venue_id
        if venue_slug is not None:
            params["venue_slug"] = venue_slug
        if historical is not None:
            params["historical"] = "true" if historical else "false"
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        return params

    def search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[EventSearchItem]:
        page = self.search_events_page(
            event_name=event_name,
            event_date=event_date,
            venue_name=venue_name,
            venue_city=venue_city,
            venue_state=venue_state,
            country_code=country_code,
            tm_event_id=tm_event_id,
            std_event_id=std_event_id,
            std_venue_id=std_venue_id,
            venue_slug=venue_slug,
            historical=historical,
            limit=limit,
        )
        return cast(List[EventSearchItem], page["data"])

    def search_events_page(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> EventSearchPage:
        params = self._search_events_params(
            event_name=event_name,
            event_date=event_date,
            venue_name=venue_name,
            venue_city=venue_city,
            venue_state=venue_state,
            country_code=country_code,
            tm_event_id=tm_event_id,
            std_event_id=std_event_id,
            std_venue_id=std_venue_id,
            venue_slug=venue_slug,
            historical=historical,
            limit=limit,
            starting_after=starting_after,
        )
        return cast(
            EventSearchPage,
            self._transport.request_json("GET", "/api/v1/events/search", params=params),
        )

    def iter_search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> PageIterator[EventSearchItem]:
        def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                self.search_events_page(
                    event_name=event_name,
                    event_date=event_date,
                    venue_name=venue_name,
                    venue_city=venue_city,
                    venue_state=venue_state,
                    country_code=country_code,
                    tm_event_id=tm_event_id,
                    std_event_id=std_event_id,
                    std_venue_id=std_venue_id,
                    venue_slug=venue_slug,
                    historical=historical,
                    limit=limit,
                    starting_after=cursor,
                ),
            )

        return PageIterator(fetch)

    def event_request_add(self, search_query: str) -> Dict[str, Any]:
        if not search_query:
            raise ValueError("search_query must be provided")
        response = self._transport.request_json(
            "POST",
            "/api/v0.4/events/event-request-add",
            json={"search_query": search_query},
            retry_safe=False,
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    def event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")
        response = self._transport.request_json(
            "GET", f"/api/v0.4/events/event-request-status/{job_id}/"
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    def download_daily_csv(self, date: Optional[str] = None) -> str:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return self._transport.request_text("GET", "/api/v0.5/daily-csv/download", params=params)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "SeatDataClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
