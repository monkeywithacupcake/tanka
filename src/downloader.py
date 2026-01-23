"""HaikuBox CSV downloader using Playwright"""

import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Download, TimeoutError as PlaywrightTimeoutError


logger = logging.getLogger(__name__)


class HaikuBoxDownloader:
    """Downloads CSV files from HaikuBox website"""

    BASE_URL = "https://listen.haikubox.com/#/haikubox"

    def __init__(self, download_dir: Path, headless: bool = True, timeout: int = 60,
                 email: str = None, password: str = None):
        """
        Initialize downloader

        Args:
            download_dir: Directory to save downloaded files
            headless: Run browser in headless mode
            timeout: Download timeout in seconds
            email: Login email for HaikuBox account
            password: Login password for HaikuBox account
        """
        self.download_dir = Path(download_dir)
        self.headless = headless
        self.timeout = timeout * 1000  # Convert to milliseconds
        self.email = email
        self.password = password

    def download_csv(self, haikubox_name: str, date: datetime) -> Optional[Path]:
        """
        Download CSV for a specific HaikuBox and date

        Args:
            haikubox_name: Name of the HaikuBox
            date: Date to download data for

        Returns:
            Path to downloaded file, or None if download failed
        """
        logger.info(f"Downloading CSV for {haikubox_name} on {date.strftime('%Y-%m-%d')}")

        with sync_playwright() as p:
            browser = p.firefox.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            try:
                # Navigate to HaikuBox page
                logger.debug(f"Navigating to {self.BASE_URL}")
                page.goto(self.BASE_URL, wait_until="networkidle")

                # Wait for page to load
                time.sleep(2)

                # Handle login if credentials provided
                if self.email and self.password:
                    if not self._handle_login(page):
                        logger.error("Login failed")
                        return None

                    # Wait for page to fully load after login
                    logger.debug("Waiting for page to load after login...")
                    time.sleep(3)

                # Change view to "All" to make Download CSV button appear
                logger.debug("Changing view to 'All'...")
                # The view button shows current selection like "View Last 2 Hours"
                view_button = page.get_by_role("button", name=re.compile(r"View"))
                view_button.wait_for(state="visible", timeout=10000)
                view_button.click()
                time.sleep(0.5)
                page.get_by_role("option", name="All").click()
                time.sleep(1)

                # Click the Download CSV button
                logger.debug("Clicking Download CSV button")
                page.get_by_role("button", name="Download CSV").click()
                time.sleep(1)

                # Unselect first option (summary) and select second option (individual detections)
                logger.debug("Selecting Individual Detections option")
                # First option is selected by default, so unselect it
                page.locator(".v-input--selection-controls__ripple.primary--text").click()
                time.sleep(0.3)
                # Select the second option (individual detections)
                page.locator("div:nth-child(2) > .v-input__control > .v-input__slot > .v-input--selection-controls__input > .v-input--selection-controls__ripple").click()
                time.sleep(0.5)

                # Select the date using button role
                logger.debug(f"Selecting date: {date.strftime('%Y-%m-%d')}")
                # this is a beast because of how the date picker is made
                # likely to have errors here
                # Calculate month difference to determine how many times to click "Previous month"
                # Calendar initially shows current month
                now = datetime.now()
                current_year = now.year
                current_month = now.month
                target_year = date.year
                target_month = date.month

                month_diff = (current_year - target_year) * 12 + (current_month - target_month)
                if month_diff == 0:
                    logger.debug(f"Target date is {month_diff} month(s) to {date.day}")
                elif month_diff > 0:
                    logger.debug(f"Target date is {month_diff} month(s) in the past, clicking Previous month {month_diff} time(s)")
                    for _ in range(month_diff):
                        page.get_by_role("button", name="Previous month").click()
                        time.sleep(0.3)
                elif month_diff < 0:
                    # Date is in the future (shouldn't happen due to check above, but handle it)
                    logger.error(f"Date is {abs(month_diff)} month(s) in the future")
                    return None

                # Now click the day
                day_str = str(date.day)  # Get day without leading zero
                page.get_by_role("button", name=day_str, exact= True).nth(0).click() # first
                time.sleep(0.5)

                # Click the Download CSV button in the dialog and wait for download
                logger.debug("Clicking Download CSV button in dialog")
                with page.expect_download(timeout=self.timeout) as download_info:
                    page.get_by_role("dialog").get_by_role("button", name="Download CSV").click()

                download = download_info.value

                # Generate filename
                filename = f"{haikubox_name}_{date.strftime('%Y-%m-%d')}.csv"
                filepath = self.download_dir / filename

                # Save the download
                download.save_as(filepath)
                logger.info(f"Successfully downloaded: {filepath}")

                return filepath

            except PlaywrightTimeoutError as e:
                logger.error(f"Timeout while downloading: {e}")
                return None
            except Exception as e:
                logger.error(f"Error downloading CSV: {e}", exc_info=True)
                return None
            finally:
                browser.close()

    def _handle_login(self, page: Page) -> bool:
        """
        Handle login to HaikuBox website

        Args:
            page: Playwright page object

        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info("Checking if login is required...")

            # Check if we're already logged in by looking for login button
            # If there's no sign in/login button, we're already logged in
            try:
                sign_in_button = page.locator("text=/sign in|log in/i").first
                if not sign_in_button.is_visible(timeout=3000):
                    logger.info("Already logged in")
                    return True
            except:
                logger.info("No login button found, assuming already logged in")
                return True

            logger.info("Logging in to HaikuBox...")

            # Click sign in/login button using role
            logger.debug("Clicking Sign In button...")
            page.get_by_role("button", name="Sign In").click()

            # Wait for login modal to appear
            logger.debug("Waiting for login modal...")
            time.sleep(2)

            # Fill in email using role-based selector
            logger.debug("Entering email...")
            email_field = page.get_by_role("textbox", name="Email Address")
            email_field.click()
            email_field.fill(self.email)

            # Fill in password using role-based selector
            logger.debug("Entering password...")
            password_field = page.get_by_role("textbox", name="Password")
            password_field.click()
            password_field.fill(self.password)

            # Click login button in the modal using role
            logger.debug("Clicking login button...")
            page.get_by_role("application").get_by_role("button", name="Sign In").click()

            # Wait for navigation after login
            time.sleep(3)

            # Verify login was successful
            # Check if we're redirected or if login elements are gone
            try:
                error_msg = page.locator("text=/error|invalid|incorrect/i").first
                if error_msg.is_visible(timeout=2000):
                    logger.error(f"Login error: {error_msg.inner_text()}")
                    return False
            except:
                pass  # No error message found, which is good

            logger.info("Login successful")
            return True

        except Exception as e:
            logger.error(f"Error during login: {e}", exc_info=True)
            return False

    def _select_date(self, page: Page, date: datetime):
        """
        Select a date from the date picker

        Args:
            page: Playwright page object
            date: Date to select
        """
        # This is a simplified date picker interaction
        # The actual implementation may need adjustment based on the specific date picker used

        # Try to find and click date input field
        try:
            # Look for input field with date/calendar icon
            date_input = page.locator("input[type='date'], input[placeholder*='date' i], .date-picker input").first
            if date_input.is_visible(timeout=2000):
                date_input.click()
                date_input.fill(date.strftime('%Y-%m-%d'))
                return
        except:
            pass

        # Alternative: Look for calendar icon or date display
        try:
            calendar_button = page.locator("[class*='calendar'], [class*='date-picker'], button:has(svg)").first
            if calendar_button.is_visible(timeout=2000):
                calendar_button.click()
                time.sleep(0.5)

                # Try to select the specific date
                # This may need adjustment based on the actual calendar implementation
                date_str = date.strftime('%-d')  # Day without leading zero
                date_locator = page.locator(f"text={date_str}").first
                date_locator.click()
                return
        except:
            pass

        logger.warning("Could not interact with date picker - may need manual intervention")

    def download_previous_day(self, haikubox_name: str) -> Optional[Path]:
        """
        Download CSV for previous day

        Args:
            haikubox_name: Name of the HaikuBox

        Returns:
            Path to downloaded file, or None if download failed
        """
        yesterday = datetime.now() - timedelta(days=1)
        return self.download_csv(haikubox_name, yesterday)

    def download_date_range(self, haikubox_name: str, start_date: datetime, end_date: datetime) -> list[Path]:
        """
        Download CSV files for a date range

        Args:
            haikubox_name: Name of the HaikuBox
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of paths to downloaded files
        """
        downloads = []
        current_date = start_date

        while current_date <= end_date:
            filepath = self.download_csv(haikubox_name, current_date)
            if filepath:
                downloads.append(filepath)
            current_date += timedelta(days=1)
            time.sleep(2)  # Delay between downloads to be respectful

        return downloads
