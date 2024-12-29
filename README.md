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

Section 3.2 of the [UCI Terms](https://ucimtbworldseries.com/terms) dictate that:

> You are not allowed to reproduce, copy, sell, modify, re-edit, communicate, distribute or use, in any way whatsoever, any content on or from the Website (including, but not limited to, logos, service marks, trademarks, trade names, photographs, illustrations, videos, articles and associated code and software), in whole or in part, otherwise than as provided for in these Terms, without our express prior written consent.

As such, no race results are posted in this repo. Rather, you may use the code in this repo to scrape results for your own use, as the UCI's [`robots.txt`](https://ucimtbworldseries.com/robots.txt) allows all user agents unrestricted access.

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

- Scrape race metadata including:
  - Course maps
  - Stage information
- Add automated testing using pytest.