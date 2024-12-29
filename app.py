import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from scraper import MTBEventsPage, MTBRacesPage, MTBResultsPage


def custom_serializer(obj):
    """Custom JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.date().isoformat()  # Convert datetime to ISO 8601 string
    raise TypeError(f"Type {type(obj)} not serializable")


if __name__ == "__main__":
    # Parse command line arguments
    description = ("Scrape MTB event results from the UCI MTB World Series "
                   "website and save them to a local folder.")
    parser = argparse.ArgumentParser(description=description)

    # Add arguments
    parser.add_argument(
        "year",
        type=int,
        help="Event year to scrape."
    )
    parser.add_argument(
        "--output", "-o",
        default="./data",
        type=Path,
        help="Output folder for the scraped data. (default: ./data)"
    )

    args = parser.parse_args()
    year = args.year
    root = args.output

    # Create the output folder if it doesn't exist
    year_folder = Path(f"{root}/{year}")
    year_folder.mkdir(parents=True, exist_ok=True)

    # Extract all event information for the given year
    event_page = MTBEventsPage(year, use_selenium=True)
    print(f"Extracting events for {year}...")
    events = event_page.fetch_events()

    # Enrich events with race information
    enriched_events = []
    for event in events:
        print(f"Extracting race info for {event['location']}...")
        enriched_event = {
            **event,
            'races': MTBRacesPage(event['results_url']).fetch_races()
        }
        enriched_events.append(enriched_event)

    # Extract results for each race and event and save
    for num, event in enumerate(enriched_events):
        # Event number for the year
        event_num = num + 1

        # Create a folder for each event for the year
        location = re.sub(r'[\s\-\–]+', '_', event["location"]) \
                     .replace(",", "") \
                     .lower()
        event_folder = year_folder / f"{event_num:02d}_{location}"
        event_folder.mkdir(parents=True, exist_ok=True)

        # Extract results for each race
        for race in event['races']:
            # Define a name for the race
            name = (f"{race['discipline']}_{race['gender']}_{race['category']}"
                    f"_{race['race_type']}")
            name = re.sub(r'\s+|-', '_', name).lower()

            # Create a folder and file for the race
            race_folder = event_folder / "results" / race['discipline']
            race_folder.mkdir(parents=True, exist_ok=True)
            race_file = race_folder / f"{name}.json"

            # Skip if the file already exists
            if race_file.exists():
                continue

            # Fetch race results
            print(f"Extracting results for {event['location']} {name}...")
            page = MTBResultsPage(race['url'])
            race['event'] = event['location']
            race.update(page.fetch_results())

            # Create a folder
            race_folder = event_folder / "results" / race['discipline']
            race_folder.mkdir(parents=True, exist_ok=True)

            # Save race results to a JSON file
            race_file = race_folder / f"{name}.json"
            with open(race_file, "w") as f:
                json.dump(race, f, default=custom_serializer,
                          ensure_ascii=False, indent=2)

            # Remove event name from each race for saving event file
            race.pop("event")

        # Save the event details to a JSON file
        event_file = event_folder / "event.json"
        with open(event_file, "w") as f:
            json.dump(event, f, default=custom_serializer,
                      ensure_ascii=False, indent=2)
