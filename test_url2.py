import json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
logging.basicConfig(level=logging.INFO)
from scraper import ExpiredDomainsScraper, logger
from config import settings

# Test with cleared cookies to see actual URL behavior
COOKIE_FILE = Path(__file__).parent / "data" / "cookies.json"
cookies_backup = None
if COOKIE_FILE.exists():
    cookies_backup = COOKIE_FILE.read_text()
    COOKIE_FILE.unlink()
    logger.info("Cleared cookies for fresh session")

# Use a simple URL with clear sort
test_url = "https://member.expireddomains.net/domains/expiredcom/?o=length&r=a&flimit=200&fonlycharhost=1&ftlds[]=2&fadult=1"

logger.info(f"Testing URL: {test_url}")

scraper = ExpiredDomainsScraper(headless=True)
try:
    scraper.start()
    scraper.login()
    scraper.navigate_to_listing()
    
    # WHAT URL are we actually on?
    actual_url = scraper.page.url
    logger.info(f"Actual URL after navigation: {actual_url}")
    
    title = scraper.page.title()
    logger.info(f"Page title: {title}")
    
    # Extract first 20 domains regardless of status
    rows = scraper.page.locator("table.base1 tbody tr, table.base1 tr").all()
    if not rows:
        rows = scraper.page.locator("tr").all()
    logger.info(f"Total rows: {len(rows)}")
    
    examples = []
    for i, row in enumerate(rows):
        cells = row.locator("td").all()
        if len(cells) < 20:
            continue
        try:
            domain = cells[0].inner_text().strip().lower()
            status = cells[22].inner_text().strip() if len(cells) > 22 else "N/A"
            reg = cells[11].inner_text().strip() if len(cells) > 11 else "0"
            length = cells[3].inner_text().strip() if len(cells) > 3 else "?"
            if len(examples) < 25:
                examples.append((domain, status, reg, length))
        except Exception:
            pass
    
    logger.info(f"First 25 domains (any status):")
    for d, s, r, l in examples:
        logger.info(f"  {d} | status={s} | reg={r} | len={l}")
        
except Exception as e:
    logger.exception("Error")
finally:
    scraper.stop()
    # Restore cookies
    if cookies_backup:
        COOKIE_FILE.write_text(cookies_backup)
        logger.info("Restored cookies")
