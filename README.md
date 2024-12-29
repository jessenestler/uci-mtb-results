# UCI Mountain Bike Results Scraper

## Overview

This project is a Python-based web scraper designed to extract detailed results, event information, and athlete data from the UCI Mountain Bike World Series official website. It leverages `BeautifulSoup` for HTML parsing, `requests` for HTTP requests, and optionally, `selenium` for JavaScript-heavy pages.

## Features

- **Event Scraping**: Fetches event details such as location, dates, disciplines, and event URLs.
- **Race Scraping**: Extracts information about individual races, including discipline, category, gender, and result links.
- **Results Scraping**: Retrieves detailed race results, including overall positions, times, gaps, points, and split/lap/stage details.

## Dependencies

- Python 3.10
- Required libraries:
  - `beautifulsoup4`
  - `requests`
  - `selenium`
  - `pydantic`

Install dependencies with:

```bash
uv install
```

## Usage

### Event Scraping

```python
from scraper import MTBEventsPage

events_page = MTBEventsPage(year=2023, use_selenium=True)
events = events_page.fetch_events()
print(events)
```

### Race Scraping

```python
from scraper import MTBRacesPage

races_url = "https://ucimtbworldseries.com/results/event/maydena-2023/2023"
races_page = MTBRacesPage(url=races_url)
races = races_page.fetch_races()
print(races)
```

### Results Scraping

```python
from scraper import MTBResultsPage

results_url = "https://ucimtbworldseries.com/results/raceCategory/maydena-edr-men-elite/2023"
results_page = MTBResultsPage(url=results_url)
results = results_page.fetch_results()
print(results)
```

## Future Improvements

- Add automated testing using pytest.