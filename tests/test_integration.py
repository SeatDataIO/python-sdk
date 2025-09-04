import os
import pytest
from seatdata import SeatDataClient, AuthenticationError, RateLimitError


@pytest.mark.integration
class TestSeatDataIntegration:
    """Integration tests that make real API calls.

    Run with: pytest tests/test_integration.py -m integration
    Requires: SEATDATA_API_KEY environment variable
    """

    @pytest.fixture
    def api_key(self):
        key = os.environ.get("SEATDATA_API_KEY")
        if not key:
            pytest.skip("SEATDATA_API_KEY environment variable not set")
        if len(key) != 64:
            pytest.skip("SEATDATA_API_KEY must be 64 characters")
        return key

    @pytest.fixture
    def client(self, api_key):
        return SeatDataClient(api_key=api_key)

    def test_search_events_real(self, client):
        """Test searching for events with real API."""
        try:
            events = client.search_events(venue_name="Madison Square Garden")
            assert isinstance(events, list)
            print(f"\nFound {len(events)} events at Madison Square Garden")

            if events:
                first_event = events[0]
                print(
                    f"First event: {first_event.get('event_name', 'N/A')} on {first_event.get('event_date', 'N/A')}"
                )
        except RateLimitError:
            pytest.skip("Rate limit hit - test later")
        except AuthenticationError:
            pytest.fail("Invalid API key")

    def test_search_events_by_name(self, client):
        """Test searching events by name."""
        try:
            events = client.search_events(event_name="Lakers")
            assert isinstance(events, list)
            print(f"\nFound {len(events)} Lakers events")
        except RateLimitError:
            pytest.skip("Rate limit hit - test later")

    def test_invalid_api_key(self):
        """Test that invalid API key raises AuthenticationError."""
        bad_client = SeatDataClient(api_key="0" * 64)

        with pytest.raises(AuthenticationError):
            bad_client.search_events(venue_name="test")

    def test_get_sales_data_real(self, client):
        """Test getting sales data with real API."""
        try:
            # First get an event_id from search
            events = client.search_events(venue_name="Madison Square Garden")
            if not events:
                pytest.skip("No events found to test with")

            event_id = str(events[0]["event_id"])
            print(f"\nTesting sales data for event: {events[0].get('event_name')} (ID: {event_id})")

            sales_data = client.get_sales_data(event_id=event_id)
            assert isinstance(sales_data, list)
            print(f"Found {len(sales_data)} sales records")

            if sales_data:
                first_sale = sales_data[0]
                print(
                    f"First sale keys: {first_sale.keys() if isinstance(first_sale, dict) else 'N/A'}"
                )
        except RateLimitError:
            pytest.skip("Rate limit hit - test later")
        except AuthenticationError:
            pytest.fail("Invalid API key")

    def test_get_listings_real(self, client):
        """Test getting listings with real API."""
        try:
            # First get an event_id from search
            events = client.search_events(venue_name="Madison Square Garden")
            if not events:
                pytest.skip("No events found to test with")

            event_id = str(events[0]["event_id"])
            print(f"\nTesting listings for event: {events[0].get('event_name')} (ID: {event_id})")

            listings = client.get_listings(event_id=event_id)
            assert isinstance(listings, dict)
            print(f"Listings keys: {listings.keys()}")

            if "listings" in listings:
                print(f"Found {len(listings['listings'])} current listings")
                active_count = sum(1 for l in listings["listings"] if l.get("active"))
                print(f"Active listings: {active_count}")
        except RateLimitError:
            pytest.skip("Rate limit hit - test later")
        except AuthenticationError:
            pytest.fail("Invalid API key")
