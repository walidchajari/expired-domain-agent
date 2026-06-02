import json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
logging.basicConfig(level=logging.INFO)
from scraper import ExpiredDomainsScraper, logger
from config import settings

scraper = ExpiredDomainsScraper(headless=True)
try:
    scraper.start()
    scraper.login()
    scraper.navigate_to_listing()
    
    page = scraper.page
    
    # Log actual URL
    logger.info(f"Current URL: {page.url}")
    
    # Check for column headers / sortable elements
    try:
        # Find the table header row
        thead = page.locator("table.base1 thead, table.base1 th").first
        if thead.is_visible():
            logger.info(f"Table header visible: {thead.inner_text()[:200]}")
        
        # Find all TH elements (column headers)
        headers = page.locator("table.base1 th").all()
        logger.info(f"Found {len(headers)} column headers")
        for i, h in enumerate(headers):
            text = h.inner_text().strip()
            # Check for sort links
            links = h.locator("a").all()
            hrefs = []
            for l in links:
                href = l.get_attribute("href") or ""
                text2 = l.inner_text().strip()
                hrefs.append(f"{text2}=>{href[:100]}")
            if hrefs:
                logger.info(f"  Header[{i}]: '{text}' links: {' | '.join(hrefs)}")
            else:
                logger.info(f"  Header[{i}]: '{text}' (no links)")
    except Exception as e:
        logger.warning(f"Could not inspect headers: {e}")
    
    # Check for filter/sort form
    try:
        forms = page.locator("form").all()
        logger.info(f"Found {len(forms)} forms on page")
        for i, form in enumerate(forms):
            action = form.get_attribute("action") or "(no action)"
            logger.info(f"  Form[{i}]: action={action[:100]}")
            # Check for sort select
            selects = form.locator("select").all()
            for s in selects:
                name = s.get_attribute("name") or "(unnamed)"
                value = s.input_value()
                opts = s.locator("option").all()
                options_str = "; ".join([f"{o.get_attribute('value')}:{o.inner_text().strip()}" for o in opts[:10]])
                logger.info(f"    Select '{name}' value='{value}' options=[{options_str}]")
    except Exception as e:
        logger.warning(f"Could not inspect forms: {e}")
    
    # Check for advanced filter toggles
    try:
        adv_link = page.locator("a:has-text('Advanced'), a:has-text('Filter'), a:has-text('Options')").first
        if adv_link.is_visible():
            logger.info(f"Advanced filter link: '{adv_link.inner_text().strip()}'")
            adv_link.click()
            page.wait_for_timeout(1000)
            # Re-check forms
            forms2 = page.locator("form").all()
            logger.info(f"After click: {len(forms2)} forms")
    except Exception as e:
        logger.warning(f"No advanced filter link: {e}")
    
    # Dump some page info
    logger.info(f"Page title: {page.title()}")
    
except Exception as e:
    logger.exception("Error")
finally:
    scraper.stop()
