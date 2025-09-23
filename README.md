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

```python
from seatdata import SeatDataClient

# Initialize client with your API key
client = SeatDataClient(api_key="your_64_char_api_key")

# Search for events
events = client.search_events(
    venue_name="Madison Square Garden",
    venue_city="New York"
)

# Get sales data for an event
sales_data = client.get_sales_data(event_id="1234567")

# Get current listings
listings = client.get_listings(event_id="1234567")

# Submit async event request (v0.2.0+)
result = client.event_request_add(search_query="Taylor Swift")
job_id = result["job_id"]

# Check job status
status = client.event_request_status(job_id=job_id)
print(f"Status: {status['status']}")
```

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