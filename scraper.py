import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator, model_validator
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class EventDetails(BaseModel):
    """Schema for event details."""
    location: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    country: Optional[str]
    disciplines: List[Optional[str]]
    event_url: Optional[str]
    results_url: Optional[str]


class RaceInfo(BaseModel):
    """Schema for race information."""
    race_name: str
    discipline: Optional[str]
    category: Optional[str]
    gender: Optional[str]
    race_type: str  # Defaults to "Finals" in the scraper logic
    url: Optional[str]


class ResultDetails(BaseModel):
    """Schema for split/lap/stage details. Depending on the race discipline,
    the details can be split, lap, or stage times."""
    section: Optional[str]  # Example: "Lap 1"
    time: Optional[str]  # Example: "10:58.541"
    gap: Optional[str]  # Example: "00:00.000"
    position: Optional[int]  # Example: 2

    @model_validator(mode="before")
    def unify_section_fields(cls, values):
        # Check for lap, split, or stage and funnel them into 'section'
        for alias in ["lap", "split", "stage"]:
            if alias in values:
                values["section"] = values.pop(alias)
                break
        return values


class RaceResult(BaseModel):
    """Schema for a race's overall results."""
    position: Optional[str] = Field(alias="#")  # Example: 1
    rider: Optional[str]  # Example: "Nino Schurter"
    nation: Optional[str]  # Example: "CHE"
    time: Optional[str]  # Example: "01:24:04"
    gap: Optional[str]  # Example: "+00:00:15"
    points: Optional[int]  # Example: 250
    team: Optional[str]  # Example: "SCOTT-SRAM MTB RACING TEAM"
    details: List[Optional[Dict]]  # Split/Lap details

    @field_validator("points", mode="before")
    def convert_non_digit_to_zero(cls, value):
        if not re.search(r"\d", str(value)):
            return 0
        return value


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

    def get(self, url: str, params: dict = None) -> BeautifulSoup:
        """Navigate to the page and return its parsed HTML."""
        if self.use_selenium:
            # Use Selenium to get the page source
            with self._create_driver() as driver:
                wait = WebDriverWait(driver, self.timeout)

                # Append query parameters to the URL
                if params:
                    url = f"{url}?{urlencode(params)}"

                driver.get(url)
                wait.until(DocumentReadyState())
                html = driver.page_source
        else:
            # Use requests to get the page source
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            html = response.text

        return BeautifulSoup(html, 'html.parser')


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
        self.soup = self.get(self.url)

    def fetch_events(self) -> List[Dict]:
        """
        Fetch and extract events from the page.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing event details.
        """
        # Locate the "Results by Event" heading
        results_heading = self._find_heading()

        if not results_heading:
            return []

        # Find all mt-1 divs under the "Results by Event" section
        mt1_divs = self._find_mt1s(results_heading)
        events = self._extract_events(mt1_divs)

        return [EventDetails(**event).model_dump() for event in events]

    def _find_heading(self) -> Optional[BeautifulSoup]:
        """
        Find the heading in the BeautifulSoup object that matches the
        specified header text.

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
        return self.soup.find(
            lambda tag: tag.name in headers and self.header in tag.text
        )

    def _find_mt1s(self, heading: BeautifulSoup) -> List[BeautifulSoup]:
        """
        This method searches for all `div` elements with the class 'mt-1' that
        are descendants of the provided `results_heading` element. On the UCI
        website, these elements correspond to cards that show event details
        rendered on mobile devices.

        Parameters
        ----------
        heading : BeautifulSoup
            A BeautifulSoup object representing the title of the Event Results
            webpage.

        Returns
        -------
        List[BeautifulSoup]
            A list of BeautifulSoup objects, each representing a `div` element
            with the class 'mt-1'.
        """
        pattern = re.compile(r'^mt-1$')
        return heading.find_all_next('div', class_=pattern)

    def _extract_events(self, divs: List[BeautifulSoup]) -> List[Dict]:
        """
        Extracts event details from the list of divs containing event
        information on the results webpage.

        Parameters
        ----------
        divs : List[BeautifulSoup]
            A list of BeautifulSoup div elements containing event information.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing details of an event:
                - 'location': The location of the event.
                - 'start_date': The start date of the event.
                - 'end_date': The end date of the event.
                - 'country': The country where the event is held.
                - 'disciplines': The disciplines involved in the event.
                - 'event_url': The URL of the event.
                - 'results_url': The URL for the event results.
        """
        events = []
        for div in divs:
            event_data = {
                'location': self._extract_location(div),
                'start_date': None,
                'end_date': None,
                'country': self._extract_country(div),
                'disciplines': self._extract_disciplines(div),
                'event_url': self._extract_event_url(div),
                'results_url': self._extract_results_url(div),
            }

            # Extract start and end dates
            date_range = self._extract_date_range(div)
            if date_range:
                event_data['start_date'], event_data['end_date'] = date_range

            events.append(event_data)

        return events

    @staticmethod
    def _extract_location(mt1_div: BeautifulSoup) -> Optional[str]:
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

    @staticmethod
    def _extract_date_range(mt1_div: BeautifulSoup) -> Optional[tuple]:
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

    @staticmethod
    def _extract_country(mt1_div: BeautifulSoup) -> Optional[str]:
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

    @staticmethod
    def _extract_disciplines(mt1_div: BeautifulSoup) -> List[str]:
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

    @staticmethod
    def _extract_event_url(mt1_div: BeautifulSoup) -> Optional[str]:
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

    @staticmethod
    def _extract_results_url(mt1_div: BeautifulSoup) -> Optional[str]:
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
        self.soup = self.get(self.url)

    def fetch_races(self) -> List[Dict]:
        """
        This method extracts race URLs and race info.

        Returns
        -------
        List[Dict]
            A list of dictionaries reprensenting each race's key information,
            such as: discipline, category, gender, race type, and url.
        """
        urls = self._extract_result_urls()
        race_info = self._extract_races()

        return [
            RaceInfo(**{**r, 'url': u}).model_dump()
            for r, u in zip(race_info, urls)
        ]

    def _extract_result_urls(self) -> List[str]:
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

    def _extract_races(self) -> List[str]:
        """
        Extracts the names of the races from the provided BeautifulSoup object.

        Returns
        -------
        List[str]
            A list of race names extracted from the headers.
        """
        headers = self.soup.find_all(lambda tag: tag.name in [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        header_text = [header.text.strip() for header in headers]
        races = list(filter(lambda x: ':' in x, header_text))
        return self._parse_race_info(races)

    def _parse_race_info(self, names: List[str]) -> List[Dict]:
        """
        Parses race information from a list of race names.

        Parameters
        ----------
        names : List[str]
            A list of race names to be parsed.

        Returns
        -------
        List[Dict]
            A list of dictionaries containing extracted race details, each
            containing:
                - race_name: str
                - discipline: str or None
                - category: str or None
                - gender: str or None
                - race_type: str or None
        """
        extracted_details = [{
            "race_name": race_name,
            "discipline": self._extract_discipline(race_name),
            "category": self._extract_category(race_name),
            "gender": self._extract_gender(race_name),
            "race_type": self._extract_race_type(race_name)
        } for race_name in names]

        return extracted_details

    @staticmethod
    def _extract_gender(race_name: str) -> Optional[str]:
        """
        Extracts the gender from a race name.

        Parameters
        ----------
        race_name : str
            The name of the race from which to extract the gender.

        Returns
        -------
        str or None
            Returns 'Men' or 'Women' if found in the race name, otherwise
            returns None.
        """
        gender_pattern = r"(Men|Women)"

        match = re.search(gender_pattern, race_name, re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _extract_category(race_name: str) -> Optional[str]:
        """
        Extracts the category from a race name string.

        Parameters
        ----------
        race_name : str
            The name of the race from which to extract the category.

        Returns
        -------
        str or None
            The extracted category if a match is found, otherwise None.

        Notes
        -----
        The function uses a regular expression to search for categories such as
        'Elite', 'U23', 'Junior', 'Youth', 'Masters 30+', etc., in a
        case-insensitive manner.
        """

        category_pattern = r"(Elite|U\d+|Junior|Youth|Master[s]?\s\d+\+)"

        match = re.search(category_pattern, race_name, re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _extract_discipline(race_name: str) -> Optional[str]:
        """
        Extracts the discipline from a given race name.

        Parameters
        ----------
        race_name : str
            The name of the race from which to extract the discipline.

        Returns
        -------
        str or None
            The extracted discipline if a match is found, otherwise None.

        Notes
        -----
        The function uses a regular expression pattern to match and extract
        the discipline from the race name. The pattern looks for disciplines
        in the format of "UCI <discipline> World Cup" or "<discipline> Racing",
        where <discipline> can include words and hyphens.
        """
        discipline_pattern = (r"UCI\s([\w-]+)\sWorld\sCup|"
                              r"((?:E-)?Enduro\s[\w-]+)\sRacing")

        match = re.match(discipline_pattern, race_name)
        if not match:
            return None
        return match.group(1) or match.group(2)

    @staticmethod
    def _extract_race_type(race_name: str) -> Optional[str]:
        """
        Extracts the race type from the given race name.

        Parameters
        ----------
        race_name : str
            The name of the race from which to extract the race type.

        Returns
        -------
        str
            The extracted race type, which can be "Qualifier", "Semi-Finals",
            or "Finals". Defaults to "Finals" if no specific race type is
            found.
        """
        type_pattern = r"(Qualifier|Semi-Finals|Finals)"

        match = re.search(type_pattern, race_name, re.IGNORECASE)
        if not match:
            return "Finals"
        return match.group(1)


class MTBResultsPage(Scraper):
    """
    Scraper class for extracting the results of a UCI World Cup event.
    """
    def __init__(self, url: str, use_selenium: bool = False,
                 timeout: int = 10):
        super().__init__(use_selenium, timeout)
        self.url = url
        self.soup = self.get(self.url)
        self.table = self._find_main_table()

    def fetch_results_date(self) -> Optional[str]:
        """
        Extract the date of the race from first header whose text matches the
        format `text:text:text:date`.

        Returns
        -------
        Optional[str]
            The header text if found, otherwise None.
        """
        # Find all headers (h1-h6)
        header_tags = self.soup.find_all(lambda tag: tag.name in [
                                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        headers = [tag.text.strip() for tag in header_tags]
        colon_headers = list(filter(lambda x: ':' in x, headers))

        for text in colon_headers:
            # Extract the last part after the last colon
            date_str = text.split(':')[-1].strip()
            potential_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            try:
                # Try to parse it into a datetime object
                # Example format: "11 Jun 2023"
                return datetime.strptime(potential_date, "%d %b %Y")
            except ValueError:
                continue  # Skip if it cannot be parsed as a date

        return None

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

        # Check if the table contains detailed results, i.e., split/lap times
        if self._has_detailed_results(headers):
            results = self._extract_results_with_details(headers, rows)
        else:
            results = self._extract_results_without_details(headers, rows)

        # Validate the extracted results
        return [RaceResult(**result).model_dump() for result in results]

    def _has_detailed_results(self, headers: List[str]) -> bool:
        """
        Determine if the table includes split/lap/stage times by checking for
        split columns or x-show rows.

        Parameters
        ----------
        headers : List[str]
            The list of column headers corresponding to the data in the row.

        Returns
        -------
        bool
            True if the table contains split/lap/stage times, otherwise False.
        """
        return self._has_detail_rows() or self._has_detail_column(headers)

    def _has_detail_rows(self) -> bool:
        """
        Check if the main table has rows with an x-show attribute, indicating
        nested split/lap/stage times.

        Returns
        -------
        bool
            True if the table contains rows with x-show attribute, otherwise
            False.
        """
        return self.table.find('tr', attrs={'x-show': True}) is not None

    @staticmethod
    def _has_detail_column(headers) -> bool:
        """
        Check if the table has columns for Splits, Laps, or Stages.

        Parameters
        ----------
        headers : List[str]
            The list of column headers corresponding to the data in the row.

        Returns
        -------
        bool
            True if the table contains a Splits, Laps, or Stages column,
            otherwise False.
        """
        headers = [header.lower() for header in headers]
        details = ['splits', 'laps', 'stages']
        return any(keyword in headers for keyword in details)

    def _extract_results_without_details(self, headers: list,
                                         rows: BeautifulSoup) -> List[Dict]:
        """
        Extracts rider results from the provided BeautifulSoup object.

        Parameters
        ----------
        headers : list of str
            The list of column headers corresponding to the data in the row.
        rows : BeautifulSoup
            The row of data from which to extract the rider's overall result.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing each athlete's results.
        """
        return [self._extract_overall_result(headers, row) for row in rows]

    def _extract_results_with_details(self, headers: list,
                                      rows: BeautifulSoup) -> List[Dict]:
        """
        Extracts rider results from the provided BeautifulSoup object.

        Some races have split/lap/stage results in a nested table. This method
        extracts the overall results and the detailed split/lap/stage results
        for each rider.

        Parameters
        ----------
        headers : list of str
            The list of column headers corresponding to the data in the row.
        rows : BeautifulSoup
            The row of data from which to extract the rider's overall result.

        Returns
        -------
        List[Dict]
            A list of dictionaries, each containing each athlete's results.
        """
        # Initialize the list to store the results
        results_data = []

        # Iterate through rows in pairs
        for i in range(0, len(rows), 2):
            overall_row = rows[i]
            overall_dict = self._extract_overall_result(headers, overall_row)

            # Process details row
            detail_row = rows[i + 1]
            detail_list = self._extract_detailed_result(detail_row)
            overall_dict["details"] = detail_list

            results_data.append(overall_dict)

        return results_data

    def _extract_overall_result(self, headers: List[str],
                                row: BeautifulSoup) -> dict:
        """
        Extracts the overall result for a rider from a given row of data.

        Parameters
        ----------
        headers : list of str
            The list of column headers corresponding to the data in the row.
        row : BeautifulSoup
            The row of data from which to extract the rider's overall result.

        Returns
        -------
        dict
            A dictionary containing the rider's information, including nation
            and team.
        """

        # Extract the rider information
        rider_info = self._extract_row_data(row)

        # Create a dictionary with the rider information
        rider_dict = {headers[j]: rider_info[j]
                      for j in range(len(rider_info))}

        # Extract the nation, rider, and team information
        rider_dict["nation"] = self._extract_nation(row)
        rider_dict.update(self._extract_rider_and_team(row))

        # Add an empty list for details
        rider_dict["details"] = []

        return rider_dict

    def _extract_detailed_result(self, row: BeautifulSoup) -> List[Dict]:
        """
        Extracts the lap/split/stage results for a rider from a given overall
        race result.

        Parameters
        ----------
        details_row : BeautifulSoup
            The row of data from which to extract the rider's detailed results.

        Returns
        -------
        List[Dict]
            A list of dictionaries containing the rider's detailed results.
        """
        # Extract the splits table
        splits_table = row.find('table')

        # Extract the headers and data from the splits table
        splits_headers, splits_table_data = self._parse_result_details(
            splits_table)

        # Parse the splits table data into a list of dictionaries
        race_details = [
            {splits_headers[k]: split[k] for k in range(len(split))}
            for split in splits_table_data
        ]

        return race_details

    def _find_main_table(self):
        """Find and return the main results table."""
        main_table = self.soup.find('table')
        if not main_table:
            raise ValueError("Main table not found.")
        return main_table

    @staticmethod
    def _standardize_header(header: str) -> str:
        """Standardize the header text."""
        return header.lower().replace(' ', '_')

    def _extract_headers(self):
        """Extract headers from the main table."""
        headers = [th.text.strip() for th in self.table.thead.find_all('th')]
        return list(map(self._standardize_header, headers))

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

    @staticmethod
    def _extract_rider_and_team(row: BeautifulSoup) -> Optional[str]:
        """Extract the rider and team name from the row."""
        links = row.find_all('a', recursive=True, href=True)
        rider = links[1].text.strip() if links else ''
        team = links[2].text.strip() if links and len(links) > 2 else ''
        return {"rider": rider, "team": team}

    def _parse_result_details(self, nested_table):
        """Parse the nested splits table."""
        details_data = []
        details_rows = self._extract_rows(nested_table)
        details_headers = list(
            map(self._standardize_header,
                self._extract_row_data(details_rows[0]))
        )

        for details_row in details_rows[1:]:  # Skip header row
            details_cols = self._extract_row_data(details_row)
            details_data.append(details_cols)

        return details_headers, details_data
