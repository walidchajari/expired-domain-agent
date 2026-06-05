import json
import re
import time
import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

COOKIE_FILE = Path(__file__).parent / "data" / "cookies.json"


class ExpiredDomainsScraper:
    LOGIN_URL = "https://www.expireddomains.net/login/"

    @property
    def TARGET_URL(self):
        if hasattr(self, '_target_url_override'):
            return self._target_url_override
        return settings.target_url

    @TARGET_URL.setter
    def TARGET_URL(self, value):
        self._target_url_override = value
    FILTERED_STATUSES = {"available", "Available"}
    MAX_LENGTH = 15
    MIN_LENGTH = 4

    # Column indices in the table (0-based)
    COL_DOMAIN = 0
    COL_LENGTH = 3
    COL_BL = 4
    COL_DP = 5
    COL_WBY = 6
    COL_ABY = 7
    COL_ACR = 8
    COL_MMGR = 9
    COL_DMOZ = 10
    COL_REG = 11
    COL_C = 12
    COL_N = 13
    COL_O = 14
    COL_B = 15
    COL_I = 16
    COL_D = 17
    COL_ADDDATE = 18
    COL_RDT = 19
    COL_STATUS = 22

    def __init__(self, headless: bool = True, timeout: int = 60000):
        self.headless = headless
        self.timeout = timeout
        self._playwright: Optional[Playwright] = None
        self._browser = None
        self._context = None
        self._page = None

    # ------------------------------------------------------------------
    # Cookie persistence
    # ------------------------------------------------------------------
    def _cookies_path(self) -> Path:
        return COOKIE_FILE

    def _sort_tracker_path(self) -> Path:
        return COOKIE_FILE.parent / "sort_column.txt"

    def _check_sort_column(self) -> None:
        """Invalidate cookies if the desired sort column changed since last login."""
        tracker = self._sort_tracker_path()
        desired_sort = settings.sort_column
        if not tracker.exists():
            if self._cookies_path().exists():
                logger.info(
                    "No sort tracker found – deleting untracked cookies"
                    " to force fresh session with sort=%s", desired_sort,
                )
                self._cookies_path().unlink()
            return
        stored_sort = tracker.read_text().strip()
        if stored_sort != desired_sort:
            logger.info(
                "Sort column changed (%s → %s) – deleting cookies for fresh session",
                stored_sort, desired_sort,
            )
            cookie_path = self._cookies_path()
            if cookie_path.exists():
                cookie_path.unlink()
            tracker.unlink()

    def _save_cookies(self) -> None:
        cookies = self._context.cookies()
        path = self._cookies_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cookies, indent=2))
        logger.info("Cookies saved (%d cookies)", len(cookies))

    def _load_cookies(self) -> bool:
        path = self._cookies_path()
        if not path.exists():
            return False
        try:
            cookies = json.loads(path.read_text())
            self._context.add_cookies(cookies)
            logger.info("Cookies loaded (%d cookies)", len(cookies))
            return True
        except Exception:
            logger.warning("Failed to load cookies")
            return False

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        logger.info("Browser started (headless=%s)", self.headless)
        self._load_cookies()

    def stop(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            logger.exception("Error stopping browser")
        logger.info("Browser stopped")

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("Browser not started – call start() first")
        return self._page

    # ------------------------------------------------------------------
    # Email auth handling
    # ------------------------------------------------------------------
    def _handle_email_auth(self) -> None:
        """Detect email auth page. In non-headless mode wait for manual completion."""
        current_url = self.page.url
        if "emailauth" not in current_url.lower():
            return

        logger.info("Email verification required – check your inbox")
        print("\n" + "=" * 60)
        print("EMAIL VERIFICATION REQUIRED")
        print("=" * 60)
        print(f"ExpiredDomains.net sent a code to {settings.expired_username}")
        print("Check your email and type the code below.")
        code = input("Code: ").strip()

        code_input = self.page.locator("#emailauth_code")
        code_input.wait_for(timeout=10000)
        code_input.fill(code)
        self.page.get_by_role("button", name="Verify").click()
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)

        if "emailauth" in self.page.url.lower():
            raise RuntimeError("Email auth failed – check the code and try again")

        logger.info("Email verification passed")
        self._save_cookies()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((PWTimeout, RuntimeError)),
        before_sleep=lambda retry_state: logger.warning(
            "Login attempt %d failed, retrying…", retry_state.attempt_number
        ),
    )
    def login(self) -> None:
        # If sort column changed, invalidate old cookies so session picks up new sort
        self._check_sort_column()

        # Try cookie-based session first
        if self._cookies_path().exists():
            logger.info("Cookies found – attempting session restore")
            self.page.goto(self.TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            if "login" not in self.page.url.lower() and "emailauth" not in self.page.url.lower():
                logger.info("Session restored from cookies")
                return
            logger.info("Cookies expired – re-authenticating")

        logger.info("Navigating to login page…")
        self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

        # If already on email auth page (previous attempt left session half-way)
        if "emailauth" in self.page.url.lower():
            logger.info("On email auth page – handling before login form")
            self._handle_email_auth()
            if "login" not in self.page.url.lower() and "emailauth" not in self.page.url.lower():
                return
            self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

        # Fill username
        username_input = self.page.locator("#inputLogin")
        username_input.wait_for(timeout=15000)
        username_input.fill(settings.expired_username)

        # Fill password
        password_input = self.page.locator("#inputPassword")
        password_input.wait_for(timeout=5000)
        password_input.fill(settings.expired_password)

        # Check "Remember Me" so the session lasts longer
        remember = self.page.locator("#rememberMe, #remember_me, input[name='remember']").first
        if remember.is_visible():
            remember.check()
            logger.info("'Remember Me' checked")

        # Submit (use role selector to distinguish Login from Search buttons)
        self.page.get_by_role("button", name="Login").click()
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)

        # Verify login success – should redirect away from /login/
        current_url = self.page.url
        if "login" in current_url.lower():
            body = self.page.content()
            if "invalid" in body.lower() or "error" in body.lower():
                raise RuntimeError("Login failed – check credentials in .env")
            raise RuntimeError("Login failed – still on login page")

        # Handle email auth if needed
        self._handle_email_auth()

        logger.info("Login successful (url=%s)", self.page.url[:80])
        self._save_cookies()
        self._sort_tracker_path().write_text(settings.sort_column)
        logger.info("Sort column saved: %s", settings.sort_column)

    # ------------------------------------------------------------------
    # Navigate to target listing
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((PWTimeout, RuntimeError)),
    )
    def navigate_to_listing(self) -> None:
        logger.info("Navigating to target listing…")
        self.page.goto(self.TARGET_URL, wait_until="domcontentloaded")
        self.page.wait_for_load_state("networkidle", timeout=60000)

        # The table might take a moment to render
        try:
            self.page.wait_for_selector("table.base1", timeout=30000)
        except PWTimeout:
            self.page.wait_for_selector("table", timeout=30000)
        logger.info("Listing page loaded (url=%s)", self.page.url[:120])

    # ------------------------------------------------------------------
    # Parse table
    # ------------------------------------------------------------------
    def extract_domains(self, pages: int = 1, filter_func=None) -> list[dict]:
        domains = []
        seen = set()
        if filter_func is None:
            filter_func = self._passes_filters
        col_map = {
            "domain": self.COL_DOMAIN,
            "length": self.COL_LENGTH,
            "bl": self.COL_BL,
            "dp": self.COL_DP,
            "wby": self.COL_WBY,
            "aby": self.COL_ABY,
            "acr": self.COL_ACR,
            "mmgr": self.COL_MMGR,
            "dmoz": self.COL_DMOZ,
            "reg": self.COL_REG,
            "reg_c": self.COL_C,
            "reg_n": self.COL_N,
            "reg_o": self.COL_O,
            "reg_b": self.COL_B,
            "reg_i": self.COL_I,
            "reg_d": self.COL_D,
            "adddate": self.COL_ADDDATE,
            "rdt": self.COL_RDT,
            "status": self.COL_STATUS,
        }

        for page_num in range(pages):
            if page_num > 0:
                offset = page_num * 200
                logger.info("Navigating to page %d (start=%d)…", page_num + 1, offset)
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

                parsed = urlparse(self.page.url.split("#")[0])
                params = parse_qs(parsed.query)
                params["start"] = [str(offset)]
                page_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(params, doseq=True),
                    "listing",
                ))
                self.page.goto(page_url, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle", timeout=60000)
                try:
                    self.page.wait_for_selector("table.base1", timeout=30000)
                except PWTimeout:
                    self.page.wait_for_selector("table", timeout=30000)
                logger.info("Page %d loaded (url=%s)", page_num + 1, self.page.url[:120])

            logger.info("Extracting domain rows from page %d…", page_num + 1)
            rows = self.page.locator("table.base1 tbody tr, table.base1 tr").all()
            if not rows:
                rows = self.page.locator("tr").all()
            logger.info("Found %d table rows", len(rows))

            page_domains = 0
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) < 20:
                    continue

                raw = self._extract_cells(cells, col_map)
                if not raw or not self._passes_prefilter(raw):
                    continue

                domain = raw["domain"]
                if domain in seen:
                    continue
                seen.add(domain)

                parsed = self._parse_metrics(raw)
                if parsed and filter_func(parsed):
                    domains.append(parsed)
                    page_domains += 1

            logger.info("Page %d yielded %d valid domains", page_num + 1, page_domains)

            # Small delay between pages to avoid rate limiting
            if page_num < pages - 1:
                import time
                time.sleep(2)

        logger.info("Extracted %d valid domains total after filtering", len(domains))
        return domains

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_cells(cells, col_map: dict) -> Optional[dict]:
        try:
            domain = cells[col_map["domain"]].inner_text().strip().lower()
            # Remove www. and clean up
            domain = domain.replace("www.", "").split("/")[0]

            def cell_text(idx):
                if idx < len(cells):
                    t = cells[idx].inner_text().strip()
                    return t.replace("\u00a0", " ").replace("\xa0", " ")
                return ""

            return {
                "domain": domain,
                "length": cell_text(col_map["length"]),
                "bl": cell_text(col_map["bl"]),
                "dp": cell_text(col_map["dp"]),
                "wby": cell_text(col_map["wby"]),
                "aby": cell_text(col_map["aby"]),
                "acr": cell_text(col_map["acr"]),
                "mmgr": cell_text(col_map["mmgr"]),
                "dmoz": cell_text(col_map["dmoz"]),
                "reg": cell_text(col_map["reg"]),
                "reg_c": cell_text(col_map["reg_c"]),
                "reg_n": cell_text(col_map["reg_n"]),
                "reg_o": cell_text(col_map["reg_o"]),
                "reg_b": cell_text(col_map["reg_b"]),
                "reg_i": cell_text(col_map["reg_i"]),
                "reg_d": cell_text(col_map["reg_d"]),
                "adddate": cell_text(col_map["adddate"]),
                "rdt": cell_text(col_map["rdt"]),
                "status": cell_text(col_map["status"]),
            }
        except Exception:
            return None

    @staticmethod
    def _passes_prefilter(raw: dict) -> bool:
        domain = raw["domain"]
        if not domain or "." not in domain:
            return False
        tld = domain.split(".")[-1]
        return tld == "com"

    @staticmethod
    def _parse_metrics(raw: dict) -> Optional[dict]:
        domain = raw["domain"]

        try:
            length = int(raw["length"]) if raw["length"].isdigit() else len(domain.replace(".com", ""))
        except (ValueError, TypeError):
            length = len(domain.replace(".com", ""))

        def safe_int(v: str) -> int:
            try:
                return int(re.sub(r"[^\d]", "", v) or 0)
            except (ValueError, TypeError):
                return 0

        def safe_str(v: str) -> str:
            return v.strip() if v else ""

        return {
            "domain": domain,
            "length": length,
            "bl": safe_str(raw.get("bl", "")),
            "dp": safe_str(raw.get("dp", "")),
            "wby": safe_str(raw.get("wby", "")),
            "aby": safe_str(raw.get("aby", "")),
            "acr": safe_str(raw.get("acr", "")),
            "mmgr": safe_str(raw.get("mmgr", "")),
            "dmoz": safe_str(raw.get("dmoz", "")),
            "reg": safe_int(raw.get("reg", "0")),
            "reg_c": safe_int(raw.get("reg_c", "0")),
            "reg_n": safe_int(raw.get("reg_n", "0")),
            "reg_o": safe_int(raw.get("reg_o", "0")),
            "reg_b": safe_int(raw.get("reg_b", "0")),
            "reg_i": safe_int(raw.get("reg_i", "0")),
            "reg_d": safe_int(raw.get("reg_d", "0")),
            "adddate": safe_str(raw.get("adddate", "")),
            "rdt": safe_str(raw.get("rdt", "")),
            "status": safe_str(raw.get("status", "")),
        }

    @staticmethod
    def _passes_threeletter_filters(parsed: dict) -> bool:
        """Filter for available exactly 3-letter .com domains (e.g. ait.com)."""
        if parsed["status"].lower() not in {"available"}:
            return False
        domain_name = parsed["domain"].replace(".com", "")
        if not re.match(r"^[a-z]{3}$", domain_name):
            return False
        l = parsed.get("length", 0)
        if l != 3:
            return False
        return True

    @staticmethod
    def _passes_threeword_filters(parsed: dict) -> bool:
        """Filter for .com domains with exactly 3 hyphen-separated words."""
        domain_name = parsed["domain"].replace(".com", "")
        if not re.match(r"^[a-z-]+$", domain_name):
            return False
        parts = domain_name.split("-")
        if len(parts) != 3:
            return False
        if any(len(p) < 2 for p in parts):
            return False
        l = parsed.get("length", 0)
        if l < 8 or l > 30:
            return False
        return True

    @staticmethod
    def _parse_numeric(value: str) -> int:
        if not value or value in ("-", "N/A", ""):
            return 0
        value = value.strip().lower().replace(",", "").replace("\u00a0", "").replace("\xa0", "")
        match = re.match(r"([\d.]+)([kmb]?)", value)
        if not match:
            return 0
        num = float(match.group(1))
        suffix = match.group(2)
        if suffix == "k":
            num *= 1000
        elif suffix == "m":
            num *= 1_000_000
        elif suffix == "b":
            num *= 1_000_000_000
        return int(num)

    def _passes_filters(self, parsed: dict) -> bool:
        # Status = Available
        if parsed["status"].lower() not in {s.lower() for s in self.FILTERED_STATUSES}:
            return False
        # Length 4-15
        l = parsed.get("length", 0)
        if l < self.MIN_LENGTH or l > self.MAX_LENGTH:
            return False
        # No numbers
        domain_name = parsed["domain"].replace(".com", "")
        if re.search(r"\d", domain_name):
            return False
        # Only a-z
        if not re.match(r"^[a-z]+$", domain_name):
            return False
        return True


# ------------------------------------------------------------------
# Convenience entry point
# ------------------------------------------------------------------
def scrape_domains(headless: bool = True, pages: int = 1) -> list[dict]:
    scraper = ExpiredDomainsScraper(headless=headless)
    try:
        scraper.start()
        scraper.login()
        scraper.navigate_to_listing()
        domains = scraper.extract_domains(pages=pages)
        logger.info("Scraping complete – %d domains from %d pages", len(domains), pages)
        return domains
    except Exception:
        logger.exception("Scraping failed")
        raise
    finally:
        scraper.stop()


THREEWORD_URL = (
    "https://member.expireddomains.net/domains/expiredcom/"
    "?o=statustld_registered&r=d&ftlds[]=2&"
    "flimit=200&fadult=1"
)


THREELETTER_URL = (
    "https://member.expireddomains.net/domains/expiredcom/"
    "?o=status&r=a&ftlds[]=2&"
    "flimit=200&fonlycharhost=1&fadult=1"
)


def scrape_threeletter_domains(headless: bool = True, pages: int = 20) -> list[dict]:
    """Scrape available 3-letter .com domains (e.g. ait.com)."""
    scraper = ExpiredDomainsScraper(headless=headless)
    try:
        scraper.start()
        scraper.login()
        scraper.TARGET_URL = THREELETTER_URL
        scraper.navigate_to_listing()
        domains = scraper.extract_domains(
            pages=pages,
            filter_func=ExpiredDomainsScraper._passes_threeletter_filters,
        )
        logger.info(
            "3-letter scraping complete – %d domains from %d pages",
            len(domains), pages,
        )
        return domains
    except Exception:
        logger.exception("3-letter scraping failed")
        raise
    finally:
        scraper.stop()


def scrape_threeword_domains(headless: bool = True, pages: int = 5) -> list[dict]:
    """Scrape hyphenated 3-word .com domains (e.g. word1-word2-word3.com)."""
    scraper = ExpiredDomainsScraper(headless=headless)
    try:
        scraper.start()
        scraper.login()
        scraper.TARGET_URL = THREEWORD_URL
        scraper.navigate_to_listing()
        domains = scraper.extract_domains(
            pages=pages,
            filter_func=ExpiredDomainsScraper._passes_threeword_filters,
        )
        logger.info(
            "3-word scraping complete – %d domains from %d pages",
            len(domains), pages,
        )
        return domains
    except Exception:
        logger.exception("3-word scraping failed")
        raise
    finally:
        scraper.stop()


def login_interactive() -> None:
    """Run once with automated credentials + manual email code entry.

    Opens a non-headless browser, fills credentials from .env,
    submits the login form, and if email verification is required,
    prompts the user to enter the code they received.
    Cookies are saved for future headless runs.
    """
    scraper = ExpiredDomainsScraper(headless=False, timeout=120000)
    try:
        scraper.start()
        # Run the automated login (fills credentials, submits, handles email auth)
        scraper._check_sort_column()

        logger.info("Navigating to login page…")
        scraper.page.goto(scraper.LOGIN_URL, wait_until="domcontentloaded")

        # If already on email auth page from a previous half-finished session
        if "emailauth" in scraper.page.url.lower():
            logger.info("On email auth page – handling verification")
            scraper._handle_email_auth()
            if "login" not in scraper.page.url.lower() and "emailauth" not in scraper.page.url.lower():
                scraper._save_cookies()
                print("Cookies saved – login complete!")
                return

        # Fill username
        username_input = scraper.page.locator("#inputLogin")
        username_input.wait_for(timeout=15000)
        username_input.fill(settings.expired_username)

        # Fill password
        password_input = scraper.page.locator("#inputPassword")
        password_input.wait_for(timeout=5000)
        password_input.fill(settings.expired_password)

        # Check "Remember Me"
        remember = scraper.page.locator("#rememberMe, #remember_me, input[name='remember']").first
        if remember.is_visible():
            remember.check()
            logger.info("'Remember Me' checked")

        # Submit
        scraper.page.get_by_role("button", name="Login").click()
        scraper.page.wait_for_load_state("domcontentloaded", timeout=30000)

        # Handle email auth interactively
        scraper._handle_email_auth()

        logger.info("Login successful (url=%s)", scraper.page.url[:80])
        scraper._save_cookies()
        scraper._sort_tracker_path().write_text(settings.sort_column)
        print("Login successful! Cookies saved for future runs.")
    except Exception:
        logger.exception("Interactive login failed")
    finally:
        scraper.stop()
