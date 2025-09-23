# SeatData SDK Examples

This directory contains example scripts showing how to use the SeatData Python SDK.

## Setup

1. Install the SDK:
```bash
pip install -e ..
```

2. Set your API key as an environment variable:
```bash
export SEATDATA_API_KEY="your_32_character_api_key_here"
```

## Examples

### basic_usage.py
Demonstrates basic SDK functionality including:
- Searching for events
- Retrieving sales data
- Getting current listings

Run it with:
```bash
python basic_usage.py
```

### async_event_request.py
Shows how to use the async event request API:
- Submit an event add request
- Poll for job completion
- Retrieve the final result

Run it with:
```bash
python async_event_request.py
```

### batch_event_requests.py
Demonstrates submitting multiple event requests:
- Submit multiple event add requests
- Track multiple job IDs
- Check status of all jobs

Run it with:
```bash
python batch_event_requests.py
```

## Getting an API Key

Contact support@seatdata.io to obtain an API key for the SeatData API.