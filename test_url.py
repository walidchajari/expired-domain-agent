import json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
logging.basicConfig(level=logging.INFO)
from scraper import ExpiredDomainsScraper, logger
from config import settings

orig_url = settings.target_url

# Test URLs:
urls = {
    "A_original+english": "https://member.expireddomains.net/domains/expiredcom/?o=statustld_registered&r=d&flimit=200&fonlycharhost=1&ftlds[]=2&fadult=1&flanguage=en",
    "B_domainpop": "https://member.expireddomains.net/domains/expiredcom/?o=domainpop&r=d&flimit=200&fonlycharhost=1&ftlds[]=2&fadult=1",
    "C_regdate": "https://member.expireddomains.net/domains/expiredcom/?o=regdate&r=d&flimit=200&fonlycharhost=1&ftlds[]=2&fadult=1",
}

ExpiredDomainsScraper.REQUIRED_REG = 0
ExpiredDomainsScraper.MAX_LENGTH = 20
ExpiredDomainsScraper.FILTERED_STATUSES = {"available", "Available", "registered", "Registered"}

for name, url in urls.items():
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing URL {name}")
    logger.info(f"{url}")
    logger.info(f"{'='*60}")
    
    settings.target_url = url
    scraper = ExpiredDomainsScraper(headless=True)
    try:
        scraper.start()
        scraper.login()
        scraper.navigate_to_listing()
        rows = scraper.page.locator("table.base1 tbody tr, table.base1 tr").all()
        if not rows:
            rows = scraper.page.locator("tr").all()
        logger.info(f"Total rows: {len(rows)}")

        examples = []
        passed_count = 0
        for i, row in enumerate(rows):
            cells = row.locator("td").all()
            if len(cells) < 20:
                continue
            try:
                domain = cells[0].inner_text().strip().lower()
                status = cells[22].inner_text().strip() if len(cells) > 22 else "N/A"
                reg = cells[11].inner_text().strip() if len(cells) > 11 else "0"
                length = cells[3].inner_text().strip() if len(cells) > 3 else "?"
                if status.lower() == "available":
                    passed_count += 1
                    if len(examples) < 30:
                        examples.append((domain, status, reg, length))
            except Exception:
                pass

        logger.info(f"Total 'available' rows: {passed_count}")
        logger.info("Sample available domains:")
        for d, s, r, l in examples[:30]:
            logger.info(f"  {d} | reg={r} | len={l}")
    except Exception as e:
        logger.exception(f"Error with {name}")
    finally:
        scraper.stop()

settings.target_url = orig_url
