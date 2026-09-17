# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-17

### Added
- `get_event_sales()` and `iter_event_sales()` on both clients - one page or a full cursor walk of `GET /api/v1/events/{event_id}/sales`. Both accept `event_id` or `event_id_sh`, plus `limit` and `source`. `get_event_sales()` also accepts `starting_after`. `iter_event_sales()` manages the cursor itself.
- `get_event_sales_batch()` on both clients - sales for up to 100 events in one `POST /api/v1/events/sales/batch` request.
- An optional `source` filter (`sh`, `vs`, `all`) on all three methods. Omitting it reproduces the previous sh-only behavior and charges.
- `first_page` on `PageIterator` and `AsyncPageIterator`, so the server's first-page-only `total_count` and `sources` survive iteration.
- New types: `SalesPage`, `SalesRow` (a discriminated union of `SHSalesRow` and `VSSalesRow`), `SourceBlock`, and a `sources` key on `BatchSalesResult`.
- `SeatDataPaymentError` for HTTP `402 Payment Required`, exported from the top-level package.

### Fixed
- `402` responses now raise `SeatDataPaymentError` SDK-wide. They previously surfaced as `SeatDataServerError` or the base `SeatDataError` depending on the response body. This also covers `get_sales_data()` and `get_listings()`.

### Deprecated
- `get_sales_data()` now emits a `DeprecationWarning` naming `get_event_sales()`. It stays on the v0.3 endpoint and will be removed in v2.0.
- Removal of `search_events_legacy()`, `event_request_add()`, and `event_request_status()` is deferred from v1.1 to v2.0.

## [1.0.0] - 2026-04-30

### Added
- Support for SeatData v1 REST API endpoints: `get_account()`, `get_usage()`, `search_events_page()`, `iter_search_events()`, `get_event_stats()`, `iter_event_stats()`.
- New `AsyncSeatDataClient` for async/await usage.
- Cursor-based auto-pagination via `PageIterator` / `AsyncPageIterator`.
- Typed response shapes (`seatdata.types.*`) for all v1 responses.
- Typed exception hierarchy: `SeatDataError`, `SeatDataAuthError`, `SeatDataRateLimitError`, `SeatDataNotFoundError`, `SeatDataInvalidRequestError`, `SeatDataSubscriptionError`, `SeatDataServerError`, `CursorExpiredError`.
- `SeatDataRateLimitError.retry_after` attribute (parsed from `Retry-After` header).
- `CursorExpiredError.items_yielded` and `.last_cursor` for resumable iteration.
- `parse_timestamp(ts)` helper for ISO-8601 UTC strings.
- Configurable retry/backoff with full jitter, honoring `Retry-After`. `max_retries` constructor argument (default 3).

### Changed
- **BREAKING:** `search_events()` now calls `GET /v1/events/search`. Removed `return_full_response=True` and `**kwargs`. Returns `List[EventSearchItem]` from one page; use `search_events_page()` for the envelope or `iter_search_events()` for auto-paginated iteration.
- HTTP layer migrated from `requests` to `httpx`. Public method signatures preserved; if you caught `requests.exceptions.*` directly, switch to catching `SeatDataError`.
- Auth header sent as `Authorization: Bearer <key>` for all requests (server still accepts the legacy `api-key` header).
- `event_request_add` → `create_event_request` (alias kept, deprecated).
- `event_request_status` → `get_event_request_status` (alias kept, deprecated).

### Deprecated
- `search_events_legacy()` - calls v0.3.1 POST search; will be removed in v1.1.
- `event_request_add()`, `event_request_status()` - use the renamed methods; aliases removed in v1.1.

### Dependencies
- Removed: `requests`.
- Added: `httpx>=0.27`, `typing_extensions>=4.0`.

## [0.3.0] - 2025-12-30

### Added
- New `download_daily_csv()` method for downloading daily event CSV files
- New exception classes: `SubscriptionError`, `NotFoundError`, `ServiceUnavailableError`
- Support for API v0.5 daily CSV download endpoint

## [0.2.0] - 2025-01-23

### Added
- New `event_request_add()` method for submitting async event add requests
- New `event_request_status()` method for checking the status of submitted jobs
- Support for 202 (Accepted) status codes in API responses
- Example scripts for using the new async event request endpoints
- Unit tests for the new endpoints

### Changed
- Improved error handling to support 404 (Not Found) status codes
- Updated README with examples of new async methods

## [0.1.1] - Previous Release

### Changed
- Minor bug fixes and improvements

## [0.1.0] - Initial Release

### Added
- Initial SDK implementation
- `search_events()` method for searching events
- `get_sales_data()` method for retrieving sales data
- `get_listings()` method for getting current listings
- Basic authentication and error handling
- Unit tests and integration tests
- Example scripts