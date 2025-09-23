import os
from seatdata import SeatDataClient


def main():
    api_key = os.environ.get("SEATDATA_API_KEY")
    if not api_key:
        print("Please set SEATDATA_API_KEY environment variable")
        print("You can get an API key from support@seatdata.io")
        return

    with SeatDataClient(api_key=api_key) as client:
        events = []

        print("\n=== Searching for Events ===")
        try:
            events = client.search_events(
                event_name="Taylor Swift",
                venue_name="Madison Square Garden",
                venue_city="New York",
                venue_state="NY",
            )
            print(f"Found {len(events)} events")
            for event in events[:3]:
                print(
                    f"- {event.get('event_name', 'N/A')} on {event.get('event_date', 'N/A')} at {event.get('venue_name', 'N/A')}"
                )
        except Exception as e:
            print(f"Error searching events: {e}")

        print("\n=== Getting Sales Data ===")
        if events and len(events) > 0:
            event_id = str(events[0]["event_id"])
            event_name = events[0].get("event_name", "Unknown")

            try:
                sales_data = client.get_sales_data(event_id=event_id)
                print(f"Retrieved sales data for {event_name} (ID: {event_id})")
                print(f"Total sales records: {len(sales_data)}")
            except Exception as e:
                print(f"Error getting sales data: {e}")

            print("\n=== Getting Current Listings ===")
            try:
                listings = client.get_listings(event_id=event_id)
                print(f"Retrieved current listings for {event_name} (ID: {event_id})")

                if "listings" in listings:
                    active_listings = [l for l in listings["listings"] if l.get("active")]
                    print(f"Active listings: {len(active_listings)}")
            except Exception as e:
                print(f"Error getting listings: {e}")
        else:
            print("No events found to get sales/listing data")


if __name__ == "__main__":
    main()
