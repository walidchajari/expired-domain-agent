import re
import time
import logging
from typing import Optional

from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)


class ExpiredDomainsScraper:
    LOGIN_URL = "https://www.expireddomains.net/login/"
    TARGET_URL = settings.target_url
    # Note: member.expireddomains.net redirects to www.expireddomains.net/login
    FILTERED_STATUSES = {"available", "Available"}
    REQUIRED_REG = 3
    MAX_LENGTH = 12
    MIN_LENGTH = 4
    MAX_WORDS = 2

    # Column indices in the table (0-based)
    COL_DOMAIN = 0
    COL_LENGTH = 3
    COL_BL = 4
    COL_DP = 5
    COL_WBY = 6
    COL_ABY = 7
    COL_ACR = 8
    COL_MMGR = 9
    COL_REG = 11
    COL_RDT = 19
    COL_STATUS = 22

    def __init__(self, headless: bool = True, timeout: int = 60000):
        self.headless = headless
        self.timeout = timeout
        self._playwright: Optional[Playwright] = None
        self._browser = None
        self._page = None

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
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        self._page = ctx.new_page()
        self._page.set_default_timeout(self.timeout)
        logger.info("Browser started (headless=%s)", self.headless)

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
        logger.info("Navigating to login page…")
        self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

        # Fill username
        username_input = self.page.locator("#inputLogin")
        username_input.wait_for(timeout=15000)
        username_input.fill(settings.expired_username)

        # Fill password
        password_input = self.page.locator("#inputPassword")
        password_input.wait_for(timeout=5000)
        password_input.fill(settings.expired_password)

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
        logger.info("Login successful (url=%s)", current_url[:80])

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
        logger.info("Listing page loaded")

    # ------------------------------------------------------------------
    # Parse table
    # ------------------------------------------------------------------
    def extract_domains(self) -> list[dict]:
        domains = []
        logger.info("Extracting domain rows…")

        rows = self.page.locator("table.base1 tbody tr, table.base1 tr").all()
        if not rows:
            rows = self.page.locator("tr").all()

        logger.info("Found %d table rows", len(rows))

        col_map = {
            "domain": self.COL_DOMAIN,
            "length": self.COL_LENGTH,
            "bl": self.COL_BL,
            "dp": self.COL_DP,
            "wby": self.COL_WBY,
            "aby": self.COL_ABY,
            "acr": self.COL_ACR,
            "mmgr": self.COL_MMGR,
            "reg": self.COL_REG,
            "rdt": self.COL_RDT,
            "status": self.COL_STATUS,
        }

        seen = set()
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
            if parsed and self._passes_filters(parsed):
                domains.append(parsed)

        logger.info("Extracted %d valid domains after filtering", len(domains))
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
                "reg": cell_text(col_map["reg"]),
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
            "reg": safe_int(raw.get("reg", "0")),
            "rdt": safe_str(raw.get("rdt", "")),
            "status": safe_str(raw.get("status", "")),
        }

    def _passes_filters(self, parsed: dict) -> bool:
        domain_name = parsed["domain"].replace(".com", "")

        # Status check (case-insensitive)
        if parsed["status"].lower() not in {s.lower() for s in self.FILTERED_STATUSES}:
            return False

        # Length
        if parsed["length"] < self.MIN_LENGTH or parsed["length"] > self.MAX_LENGTH:
            return False

        # Registered in at least N extensions
        if parsed["reg"] < self.REQUIRED_REG:
            return False

        # No numbers
        if re.search(r"\d", domain_name):
            return False

        # No special characters (only a-z)
        if not re.match(r"^[a-z]+$", domain_name):
            return False

        # Max 2 words (rough heuristic: count possible word boundaries)
        words = re.findall(r"[a-z]{2,}", domain_name)
        if len(words) > self.MAX_WORDS:
            return False

        return True


# ------------------------------------------------------------------
# Convenience entry point
# ------------------------------------------------------------------
def scrape_domains(headless: bool = True) -> list[dict]:
    scraper = ExpiredDomainsScraper(headless=headless)
    try:
        scraper.start()
        scraper.login()
        scraper.navigate_to_listing()
        domains = scraper.extract_domains()
        logger.info("Scraping complete – %d domains", len(domains))
        return domains
    except Exception:
        logger.exception("Scraping failed")
        raise
    finally:
        scraper.stop()
