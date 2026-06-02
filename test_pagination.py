import json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
logging.basicConfig(level=logging.INFO)
from scraper import ExpiredDomainsScraper, logger
from config import settings

# Test if fpage parameter works
scraper = ExpiredDomainsScraper(headless=True)
try:
    scraper.start()
    scraper.login()
    scraper.navigate_to_listing()
    
    page = scraper.page
    
    # Check for pagination elements
    try:
        pagination_links = page.locator("a:has-text('Next'), a:has-text('next'), a[rel='next'], .pagination a, .paging a, a[href*='fpage']").all()
        logger.info(f"Found {len(pagination_links)} pagination links")
        for link in pagination_links:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
            logger.info(f"  '{text}' -> {href[:120]}")
    except Exception as e:
        logger.warning(f"Pagination search error: {e}")
    
    # Check for page numbers
    try:
        page_links = page.locator("a").all()
        fpage_links = []
        for link in page_links:
            href = link.get_attribute("href") or ""
            if "fpage=" in href:
                fpage_links.append((link.inner_text().strip(), href))
        logger.info(f"Found {len(fpage_links)} links with fpage parameter:")
        for text, href in fpage_links[:10]:
            logger.info(f"  '{text}' -> {href[:150]}")
    except Exception as e:
        logger.warning(f"fpage search error: {e}")
    
    # Try accessing page 2 directly
    current = page.url
    logger.info(f"Current URL: {current}")
    
    # Add fpage=2
    if "fpage=" in current:
        url2 = current.replace("fpage=" + (current.split("fpage=")[1].split("&")[0] if "&" in current.split("fpage=")[1] else ""), "fpage=2")
    else:
        separator = "&" if "?" in current else "?"
        url2 = current + separator + "fpage=2"
    
    logger.info(f"Trying page 2: {url2[:150]}")
    page.goto(url2, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    logger.info(f"URL after page 2 nav: {page.url}")
    
    rows = page.locator("table.base1 tbody tr, table.base1 tr").all()
    if not rows:
        rows = page.locator("tr").all()
    logger.info(f"Rows on page 2: {len(rows)}")
    
    if len(rows) > 0:
        first_cells = rows[0].locator("td").all()
        if len(first_cells) > 0:
            logger.info(f"First domain on page 2: {first_cells[0].inner_text().strip()}")
    
except Exception as e:
    logger.exception("Error")
finally:
    scraper.stop()
