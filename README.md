# SeatData Python SDK

[![PyPI version](https://img.shields.io/pypi/v/seatdata-sdk.svg)](https://pypi.org/project/seatdata-sdk/)
[![Tests](https://github.com/SeatDataIO/python-sdk/actions/workflows/test.yml/badge.svg)](https://github.com/SeatDataIO/python-sdk/actions/workflows/test.yml)
[![Python Support](https://img.shields.io/pypi/pyversions/seatdata-sdk)](https://pypi.org/project/seatdata-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Official Python SDK for SeatData API - access ticket sales data, event listings, and search functionality.

## Installation

```bash
pip install seatdata-sdk
```

## Quick Start

### Sync

```python
from seatdata import SeatDataClient

client = SeatDataClient(api_key="your_64_char_api_key")

# Verify auth + see your plans and rate limits
account = client.get_account()
print(account["plans"])

# Search events (v1) — returns list of items from one page
events = client.search_events(venue_name="Madison Square Garden", venue_city="New York")

# Or iterate all matching events across pages
for event in client.iter_search_events(event_name="Taylor Swift"):
    print(event["event_id"], event["event_name"])

# Get event-level price/listing time series
for snapshot in client.iter_event_stats(event_id=12345):
    print(snapshot["timestamp"], snapshot["get_in"], snapshot["avg_price"])

# v0.x endpoints continue to work
sales = client.get_sales_data(event_id="1234567")
listings = client.get_listings(event_id="1234567")
csv = client.download_daily_csv()  # latest day
```

### Async

```python
import asyncio
from seatdata import AsyncSeatDataClient


async def main():
    async with AsyncSeatDataClient(api_key="your_64_char_api_key") as client:
        events = await client.search_events(event_name="Taylor Swift")
        async for snapshot in client.iter_event_stats(events[0]["event_id"]):
            print(snapshot["timestamp"], snapshot["get_in"])


asyncio.run(main())
```

## Migrating from v0.3.x

- `search_events()` now calls `GET /v1/events/search` and returns the v1 envelope's `data`. The legacy `POST /v0.3.1/events/search` is available as `search_events_legacy()` (deprecated, removed in v1.1).
- `event_request_add` → `create_event_request`. `event_request_status` → `get_event_request_status`. Old names remain as deprecated aliases.
- Exceptions gained richer attributes: `SeatDataRateLimitError.retry_after`, `SeatDataInvalidRequestError.param`, `CursorExpiredError.items_yielded` / `.last_cursor`. Legacy exception names (`AuthenticationError`, `RateLimitError`, etc.) are preserved as aliases.
- The HTTP layer is now `httpx`. If you caught `requests.exceptions.*` directly, switch to `seatdata.SeatDataError`.

## API Key

Contact support@seatdata.io to obtain an API key.

## Development

```bash
# Clone the repository
git clone https://github.com/SeatDataIO/python-sdk.git
cd python-sdk

# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run integration tests (requires API key)
export SEATDATA_API_KEY="your_api_key"
pytest -m integration
```

## License

MIT