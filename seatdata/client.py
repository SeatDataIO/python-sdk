import warnings
from typing import Any, Dict, List, Optional, Sequence, Union, cast

from ._batch import normalize_batch_response, prepare_batch_payload
from ._sales import resolve_sales_id, build_event_sales_params
from ._transport import _Transport
from .exceptions import SeatDataError
from .pagination import PageIterator
from .types import (
    AccountResponse,
    BatchSalesResult,
    EventSearchItem,
    EventSearchPage,
    EventStatsPage,
    EventStatsSnapshot,
    SalesPage,
    SalesRow,
    UsageResponse,
)


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
        warnings.warn(
            "get_sales_data() calls the v0.3 endpoint and returns sh rows only. "
            "Use get_event_sales() for v1 sales, the source filter, and pagination. "
            "This method will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
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

    def get_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SalesPage:
        """Fetch one page of sales for an event.

        Retries follow the client's max_retries setting, 3 by default.
        Construct the client with max_retries=0 to disable them.

        total_count and sources appear on the first page only.

        See https://docs.seatdata.io/docs/api/ for pricing.
        """
        path_id, id_type = resolve_sales_id(event_id, event_id_sh)
        params = build_event_sales_params(
            limit=limit,
            starting_after=starting_after,
            source=source,
            id_type=id_type,
        )
        return cast(
            SalesPage,
            self._transport.request_json("GET", f"/api/v1/events/{path_id}/sales", params=params),
        )

    def iter_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> PageIterator[SalesRow]:
        """Walk every page of sales for an event.

        source, limit, and the id pair are fixed for the life of the iterator.
        Cursors are bound to the source they were issued under, so changing
        source mid-walk is not supported. Read total_count and sources from
        the iterator's first_page attribute after the first item.
        """
        resolve_sales_id(event_id, event_id_sh)

        def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                self.get_event_sales(
                    event_id=event_id,
                    event_id_sh=event_id_sh,
                    limit=limit,
                    starting_after=cursor,
                    source=source,
                ),
            )

        return PageIterator(fetch)

    def get_event_sales_batch(
        self,
        event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
        event_ids: Optional[Sequence[Union[int, str]]] = None,
        source: Optional[str] = None,
    ) -> BatchSalesResult:
        """Fetch sales for up to 100 events in one request.

        This call is never retried automatically, because the endpoint is not
        idempotent: a timeout may mean the server processed the request and the
        response was lost, not that nothing happened. A caller who accepts that
        risk can retry in their own code.

        A 402 response raises SeatDataPaymentError. A per-event failure is
        data, and arrives as "payment_required" in errors.

        results, errors, and sources are all keyed by the decimal string of
        each id sent.

        See https://docs.seatdata.io/docs/api/ for pricing.
        """
        payload = prepare_batch_payload(event_ids_sh, event_ids)
        params: Dict[str, Any] = {}
        if source is not None:
            params["source"] = source
        response = self._transport.request_json(
            "POST",
            "/api/v1/events/sales/batch",
            params=params,
            json=payload,
            retry_safe=False,
        )
        return normalize_batch_response(response)

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

    def _event_stats_params(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        return params

    def get_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> EventStatsPage:
        params = self._event_stats_params(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            starting_after=starting_after,
        )
        return cast(
            EventStatsPage,
            self._transport.request_json("GET", f"/api/v1/events/{event_id}/stats", params=params),
        )

    def iter_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> PageIterator[EventStatsSnapshot]:
        def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                self.get_event_stats(
                    event_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    starting_after=cursor,
                ),
            )

        return PageIterator(fetch)

    def create_event_request(self, search_query: str) -> Dict[str, Any]:
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

    def event_request_add(self, search_query: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_add() is deprecated. Use create_event_request() instead. "
            "This alias will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.create_event_request(search_query)

    def get_event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")
        response = self._transport.request_json(
            "GET", f"/api/v0.4/events/event-request-status/{job_id}/"
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    def event_request_status(self, job_id: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_status() is deprecated. Use get_event_request_status() instead. "
            "This alias will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_event_request_status(job_id)

    def download_daily_csv(self, date: Optional[str] = None) -> str:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return self._transport.request_text("GET", "/api/v0.5/daily-csv/download", params=params)

    def search_events_legacy(
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
            "search_events_legacy() calls the deprecated v0.3.1 POST endpoint. "
            "Use search_events() (v1 GET) instead. This method will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        search_params: Dict[str, Any] = {}
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
        response = self._transport.request_json(
            "POST", "/api/v0.3.1/events/search", json=search_params
        )
        if return_full_response:
            return response
        if isinstance(response, dict) and "items" in response:
            return response["items"]
        return response

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "SeatDataClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
