import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class DocumentReadyState:
    """Wait until the document is in the specified state."""
    def __init__(self, state="complete"):
        self.state = state

    def __call__(self, driver):
        ready_state = driver.execute_script("return document.readyState")
        return ready_state == self.state


class Scraper:
    """Base class for all page scrapers."""

    def __init__(self,  use_selenium: bool, timeout: int = 10):
        """Initialize the PageScraper class."""
        self.use_selenium = use_selenium
        self.timeout = timeout

    def _create_driver(self):
        """Create a Chrome driver instance."""
        service = Service()
        options = webdriver.ChromeOptions()
        options.headless = True
        return webdriver.Chrome(service=service, options=options)

    def get(self, url: str, params: dict = None) -> str:
        """Navigate to the page and return its HTML."""
        if self.use_selenium:
            # Use Selenium to get the page source
            with self._create_driver() as driver:
                wait = WebDriverWait(driver, self.timeout)

                # Append query parameters to the URL
                if params:
                    url = f"{url}?{urlencode(params)}"

                driver.get(url)
                wait.until(DocumentReadyState())
                return driver.page_source
        else:
            # Use requests to get the page source
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.text


class MTBEventsPage(Scraper):
    """
    Scraper class for extracting mountain bike event details from the UCI
    official website.
    """
    base_url = "https://ucimtbworldseries.com/results"
    header = "Results by Event"

    def __init__(self, year: int = None, use_selenium: bool = False,
                 timeout: int = 10):
        """
        Initialize the MTBEventPage scraper.

        Parameters
        ----------
        url : str
            The URL of the page to scrape.
        timeout : int, optional
            Timeout in seconds for the web driver, by default 10.
        """
        super().__init__(use_selenium, timeout)
        self.year = year
        self.url = f"{self.base_url}/{self.year}" if year else self.base_url

    def fetch_events(self, params: dict = None) -> List[Dict]:
        """
        Fetch and extract events from the page.

        Parameters
        ----------
        params : dict, optional
            Query parameters to append to the URL, by default None.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing event details.
        """
        html_content = self.get(self.url, params)
        soup = BeautifulSoup(html_content, 'html.parser')
        return self._extract_events(soup)

    def _extract_events(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract event details from the parsed HTML.

        Parameters
        ----------
        soup : BeautifulSoup
            Parsed HTML content.

        Returns
        -------
        List[Dict]
            A list of dictionaries where each dictionary contains event
            details.
        """
        events = []

        # Locate the "Results by Event" heading
        results_heading = self._find_heading(soup)

        if results_heading:
            # Find all mt-1 divs under the "Results by Event" section
            mt1_divs = self._find_mt1(results_heading)
            for mt1_div in mt1_divs:
                events.append(self._extract_event_details(mt1_div))

        return events

    def _find_heading(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Find the heading in the BeautifulSoup object that matches the
        specified header text.

        Parameters
        ----------
        soup : BeautifulSoup
            The BeautifulSoup object to search within.

        Returns
        -------
        Optional[BeautifulSoup]
            The first heading tag that matches the specified header text,
            or None if no match is found.

        Notes
        -----
        The method searches for tags 'h1' through 'h6' and checks if the
        specified header text is present in the tag's text.
        """
        headers = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        return soup.find(
            lambda tag: tag.name in headers and self.header in tag.text
        )

    def _find_mt1(self, results_heading: BeautifulSoup) -> List[BeautifulSoup]:
        """
        This method searches for all `div` elements with the class 'mt-1' that
        are descendants of the provided `results_heading` element. On the UCI
        website, these elements correspond to cards that show event details
        rendered on mobile devices.

        Parameters
        ----------
        results_heading : BeautifulSoup
            A BeautifulSoup object representing the header for results by
            event.

        Returns
        -------
        List[BeautifulSoup]
            A list of BeautifulSoup objects, each representing a `div` element
            with the class 'mt-1'.
        """
        pattern = re.compile(r'^mt-1$')
        return results_heading.find_all_next('div', class_=pattern)

    def _extract_event_details(self, mt1_div: BeautifulSoup) -> Dict:
        """
        Extracts event details from a BeautifulSoup object representing an
        event.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object containing the HTML of the event.

        Returns
        -------
        Dict
            A dictionary containing the event details with the following keys:
            - 'location': str or None
            - 'start_date': str or None
            - 'end_date': str or None
            - 'country': str or None
            - 'disciplines': list of str or None
            - 'event_url': str or None
            - 'results_url': str or None
        """
        event_data = {
            'location': self._extract_location(mt1_div),
            'start_date': None,
            'end_date': None,
            'country': self._extract_country(mt1_div),
            'disciplines': self._extract_disciplines(mt1_div),
            'event_url': self._extract_event_url(mt1_div),
            'results_url': self._extract_results_url(mt1_div),
        }

        # Extract start and end dates
        date_range = self._extract_date_range(mt1_div)
        if date_range:
            event_data['start_date'], event_data['end_date'] = date_range

        return event_data

    def _extract_location(self, mt1_div: BeautifulSoup) -> Optional[str]:
        """
        Extracts the location from the given BeautifulSoup object.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object containing the HTML div elements
            from which the location is to be extracted.
        Returns

        -------
        Optional[str]
            The extracted location as a string if available, otherwise None.
        """
        details = mt1_div.find_all('div')
        return details[1].text.strip() if len(details) >= 1 else None

    def _extract_date_range(self, mt1_div: BeautifulSoup) -> Optional[tuple]:
        """
        Extracts a date range from the provided BeautifulSoup object.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object containing the HTML div elements with date
            information.

        Returns
        -------
        Optional[tuple]
            A tuple containing two datetime objects representing the start and
            end dates if a range is found.
            If only a single date is found, the tuple will contain the same
            date twice.
            Returns None if no valid date is found or if there is a parsing
            error.

        Notes
        -----
        The function expects the date range to be in the format
        "Day - Day Month YYYY" or "Day Month YYYY".
        """
        details = mt1_div.find_all('div')
        if len(details) >= 2:
            date_range = details[0].text.strip()

            # Match the pattern "1 - 4 Month YYYY"
            dual_day = r'(\d+)\s*-\s*(\d+)\s*([A-Za-z]+)\s*(\d{4})'
            match = re.match(dual_day, date_range)
            if match:
                day_start, day_end, month, year = match.groups()
                try:
                    start_date = datetime.strptime(
                        f"{day_start} {month} {year}", "%d %B %Y")
                    end_date = datetime.strptime(
                        f"{day_end} {month} {year}", "%d %B %Y")
                    return start_date, end_date
                except ValueError:
                    return None

            # If only one date is provided, e.g., "4 May 2024"
            single_day = r'(\d+)\s*([A-Za-z]+)\s*(\d{4})'
            match_single = re.match(single_day, date_range)
            if match_single:
                day, month, year = match_single.groups()
                try:
                    single_date = datetime.strptime(
                        f"{day} {month} {year}", "%d %B %Y")
                    return single_date, single_date
                except ValueError:
                    return None

        return None

    def _extract_country(self, mt1_div: BeautifulSoup) -> Optional[str]:
        """
        Extracts the country code from the given BeautifulSoup div element.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            The BeautifulSoup div element containing the country flag.

        Returns
        -------
        Optional[str]
            The country code if found, otherwise None.
        """
        preceding_div = mt1_div.find_previous_sibling('div')
        if preceding_div:
            flag_svg = preceding_div.find(
                'svg', id=lambda x: x and x.startswith('flag-'))
            if flag_svg:
                return flag_svg.get('id', '').replace('flag-', '')
        return None

    def _extract_disciplines(self, mt1_div: BeautifulSoup) -> List[str]:
        """
        Extracts a list of disciplines from the given BeautifulSoup object.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object representing the starting div element.

        Returns
        -------
        List[str]
            A list of discipline names extracted from the 'alt' attribute of
            'img' tags in the proceeding sibling div. Returns an empty list
            if no proceeding sibling div or 'img' tags are found.
        """
        proceeding_div = mt1_div.find_next_sibling('div')
        if proceeding_div:
            imgs = proceeding_div.find_all('img', alt=True)
            return [img['alt'] for img in imgs]
        return []

    def _extract_event_url(self, mt1_div: BeautifulSoup) -> Optional[str]:
        """
        Extracts the event URL from a given BeautifulSoup div element.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object representing a div element.

        Returns
        -------
        Optional[str]
            The URL string if the parent anchor tag is found, otherwise None.
        """
        parent_anchor = mt1_div.find_parent('a')
        return parent_anchor.get('href') if parent_anchor else None

    def _extract_results_url(self, mt1_div: BeautifulSoup) -> Optional[str]:
        """
        Extracts the URL of the results page from the given BeautifulSoup
        object.

        Parameters
        ----------
        mt1_div : BeautifulSoup
            A BeautifulSoup object representing a specific div element.

        Returns
        -------
        Optional[str]
            The URL of the results page if found, otherwise None.
        """
        parent_div = mt1_div.find_parent('div')
        if parent_div:
            results_div = parent_div.find_next_sibling('div')
            if results_div:
                results_link = results_div.find(
                    'a', href=lambda x: x and 'result' in x.lower())
                return results_link.get('href') if results_link else None
        return None


class MTBRacesPage(Scraper):
    """
    Scraper class for extracting links for results of every race at a UCI
    World Cup event.
    """
    def __init__(self, url: str, use_selenium: bool = False,
                 timeout: int = 10):
        super().__init__(use_selenium, timeout)
        self.url = url
        self.soup = self._create_soup()

    def _create_soup(self) -> BeautifulSoup:
        """
        Create a BeautifulSoup object from the page source.

        Returns
        -------
        BeautifulSoup
            The parsed HTML content of the page.
        """
        html_content = self.get(self.url)
        return BeautifulSoup(html_content, 'html.parser')

    def fetch_result_urls(self) -> List[str]:
        """
        Extracts links for every race results page from the provided
        BeautifulSoup object.

        Returns
        -------
        List[str]
            A list of URLs to the results
        """
        result_links = self.soup.find_all(
            'a', href=lambda x: x and 'results/' in x.lower())
        return [link.get('href') for link in result_links]


class MTBResultsPage(Scraper):
    """
    Scraper class for extracting the results of a UCI World Cup event.
    """
    def __init__(self, url: str, use_selenium: bool = False,
                 timeout: int = 10):
        super().__init__(use_selenium, timeout)
        self.url = url
        self.soup = self._create_soup()
        self.table = self._find_main_table()

    def _create_soup(self) -> BeautifulSoup:
        """
        Create a BeautifulSoup object from the page source.

        Returns
        -------
        BeautifulSoup
            The parsed HTML content of the page.
        """
        html_content = self.get(self.url)
        return BeautifulSoup(html_content, 'html.parser')

    def fetch_results(self) -> List[Dict]:
        """
        Extracts the results from the provided BeautifulSoup object.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing each athlete's results.
        """
        headers = self._extract_headers()
        rows = self._extract_rows(self.table)

        results_data = []

        # Iterate through rows in pairs
        for i in range(0, len(rows), 2):
            high_level_row = rows[i]
            rider_info = self._extract_row_data(high_level_row)
            rider_dict = {headers[j]: rider_info[j]
                          for j in range(len(rider_info))}
            rider_dict["Nation"] = self._extract_nation(high_level_row)

            # Process details row
            details_row = rows[i + 1]
            splits_table = details_row.find('table')
            splits_headers, splits_table_data = self._parse_result_details(
                splits_table)
            race_details = [
                {splits_headers[k]: split[k] for k in range(len(split))}
                for split in splits_table_data
            ]
            rider_dict["Race Details"] = race_details

            results_data.append(rider_dict)

        return results_data

    def _find_main_table(self):
        """Find and return the main results table."""
        main_table = self.soup.find('table')
        if not main_table:
            raise ValueError("Main table not found.")
        return main_table

    def _extract_headers(self):
        """Extract headers from the main table."""
        return [th.text.strip() for th in self.table.thead.find_all('th')]

    @staticmethod
    def _extract_rows(table):
        """Extract all rows from the main table body."""
        try:
            return table.tbody.find_all('tr', recursive=False)
        except AttributeError:
            return table.find_all('tr', recursive=False)

    @staticmethod
    def _extract_row_data(row):
        """Parse a high-level row (odd rows)."""
        return [td.text.strip() for td in row.find_all('td')]

    @staticmethod
    def _extract_nation(row: BeautifulSoup) -> Optional[str]:
        """Extract the nation from the row's SVG flag tag."""
        svg = row.find('svg', recursive=True,
                       id=lambda x: x and x.startswith('flag-'))
        return svg['id'].replace('flag-', '').upper() if svg else None

    def _parse_result_details(self, nested_table):
        """Parse the nested splits table."""
        details_data = []
        details_rows = self._extract_rows(nested_table)
        details_headers = self._extract_row_data(details_rows[0])

        for details_row in details_rows[1:]:  # Skip header row
            details_cols = self._extract_row_data(details_row)
            details_data.append(details_cols)

        return details_headers, details_data
