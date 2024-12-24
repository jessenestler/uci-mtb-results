from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urlencode


class DocumentReadyState:
    """Wait until the document is in the specified state."""
    def __init__(self, state="complete"):
        self.state = state

    def __call__(self, driver):
        ready_state = driver.execute_script("return document.readyState")
        return ready_state == self.state


class Scraper:
    """Base class for all page scrapers."""

    def __init__(self, timeout: int = 10):
        """Initialize the PageScraper class."""
        self.timeout = timeout
        self.driver = self._driver
        self.wait = WebDriverWait(self.driver, self.timeout)

    @property
    def _driver(self):
        """Return a Chrome driver instance."""
        service = Service()
        options = webdriver.ChromeOptions()
        options.headless = True
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    def get(self, url: str, params: dict = None) -> str:
        """Navigate to the page and return its HTML."""
        # Append query parameters to the URL
        if params:
            url = f"{url}?{urlencode(params)}"

        # Get the page url
        self.driver.get(url)
        self.wait.until(DocumentReadyState())

        return self.driver.page_source
