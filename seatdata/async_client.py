import warnings
from typing import Any, Dict, List, Optional, cast

from ._transport import _Transport
from .exceptions import SeatDataError
from .pagination import AsyncPageIterator
from .types import (
    AccountResponse,
    EventSearchItem,
    EventSearchPage,
    EventStatsPage,
    EventStatsSnapshot,
    UsageResponse,
)


class AsyncSeatDataClient:
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

    async def get_account(self) -> AccountResponse:
        return cast(AccountResponse, await self._transport.arequest_json("GET", "/api/v1/account"))

    async def get_usage(self) -> UsageResponse:
        return cast(UsageResponse, await self._transport.arequest_json("GET", "/api/v1/usage"))

    async def search_events(
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
        page = await self.search_events_page(
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

    async def search_events_page(
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
        return cast(
            EventSearchPage,
            await self._transport.arequest_json("GET", "/api/v1/events/search", params=params),
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
    ) -> AsyncPageIterator[EventSearchItem]:
        async def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                await self.search_events_page(
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

        return AsyncPageIterator(fetch)

    async def get_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> EventStatsPage:
        params: Dict[str, Any] = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        return cast(
            EventStatsPage,
            await self._transport.arequest_json(
                "GET", f"/api/v1/events/{event_id}/stats", params=params
            ),
        )

    def iter_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncPageIterator[EventStatsSnapshot]:
        async def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                await self.get_event_stats(
                    event_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    starting_after=cursor,
                ),
            )

        return AsyncPageIterator(fetch)

    async def get_sales_data(
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
            await self._transport.arequest_json("GET", "/api/v0.3/salesdata/get", params=params),
        )

    async def get_listings(
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
            await self._transport.arequest_json("GET", "/api/v0.1/listings/get", params=params),
        )

    async def download_daily_csv(self, date: Optional[str] = None) -> str:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return await self._transport.arequest_text(
            "GET", "/api/v0.5/daily-csv/download", params=params
        )

    async def create_event_request(self, search_query: str) -> Dict[str, Any]:
        if not search_query:
            raise ValueError("search_query must be provided")
        response = await self._transport.arequest_json(
            "POST",
            "/api/v0.4/events/event-request-add",
            json={"search_query": search_query},
            retry_safe=False,
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    async def get_event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")
        response = await self._transport.arequest_json(
            "GET", f"/api/v0.4/events/event-request-status/{job_id}/"
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    async def event_request_add(self, search_query: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_add() is deprecated. Use create_event_request() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.create_event_request(search_query)

    async def event_request_status(self, job_id: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_status() is deprecated. Use get_event_request_status() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.get_event_request_status(job_id)

    async def search_events_legacy(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        return_full_response: bool = False,
        **kwargs: Any,
    ) -> Any:
        warnings.warn(
            "search_events_legacy() is deprecated. Use search_events() (v1 GET) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        params: Dict[str, Any] = {}
        if event_name:
            params["event_name"] = event_name
        if event_date:
            params["event_date"] = event_date
        if venue_name:
            params["venue_name"] = venue_name
        if venue_city:
            params["venue_city"] = venue_city
        if venue_state:
            params["venue_state"] = venue_state
        params.update(kwargs)
        response = await self._transport.arequest_json(
            "POST", "/api/v0.3.1/events/search", json=params
        )
        if return_full_response:
            return response
        if isinstance(response, dict) and "items" in response:
            return response["items"]
        return response

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> "AsyncSeatDataClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()
