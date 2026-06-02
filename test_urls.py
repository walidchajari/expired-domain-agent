"""Scrape 3 different ExpiredDomains.net URLs, show first 15 domain names from each.
Uses correct URL parameter names discovered from the site's table headers."""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_urls")
logging.getLogger("scraper").setLevel(logging.DEBUG)

BASE = "https://member.expireddomains.net/domains/expiredcom/"

# CORRECTED parameter names (from actual site header links)
URL_A = BASE + "?o=length&r=a&flimit=200&fonlycharhost=1&fnohyphens=1&fminlen=5&fmaxlen=10&fadult=1&ftlds[]=2"
URL_B = BASE + "?o=statustld_registered&r=d&flimit=200&fonlycharhost=1&fnohyphens=1&fminbl=5&fadult=1&ftlds[]=2"
URL_C = BASE + "?o=domainpop&r=d&flimit=200&fonlycharhost=1&fnohyphens=1&fadult=1&ftlds[]=2"

from scraper import ExpiredDomainsScraper


def scrape_url_raw(url, label):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  URL: {url}")
    sys.stdout.flush()

    scraper = ExpiredDomainsScraper(headless=True)
    scraper.TARGET_URL = url

    try:
        scraper.start()
        scraper.login()
        scraper.navigate_to_listing()

        # Final URL after all redirects
        final_url = scraper.page.url
        print(f"  [FINAL URL] {final_url}")
        sys.stdout.flush()

        # Extract raw domain names from column 0
        rows = scraper.page.locator("table.base1 tbody tr, table.base1 tr").all()
        if not rows:
            rows = scraper.page.locator("tr").all()
        print(f"  [ROWS] {len(rows)} table rows found")

        raw_domains = []
        seen = set()
        for row in rows:
            cells = row.locator("td").all()
            if len(cells) < 3:
                continue
            try:
                domain = cells[0].inner_text().strip().lower()
                domain = domain.replace("www.", "").split("/")[0]
                if "." not in domain or domain in seen:
                    continue
                # Grab a few extra columns for context
                length = cells[3].inner_text().strip() if len(cells) > 3 else "?"
                bl = cells[4].inner_text().strip() if len(cells) > 4 else "?"
                reg = cells[11].inner_text().strip() if len(cells) > 11 else "?"
                status_text = cells[22].inner_text().strip() if len(cells) > 22 else "?"
                seen.add(domain)
                raw_domains.append((domain, length, bl, reg, status_text))
                if len(raw_domains) >= 20:
                    break
            except Exception:
                continue

        print(f"\n  >>> First {len(raw_domains)} domains (domain, len, BL, reg, status):")
        for i, (d, ln, bl, reg, st) in enumerate(raw_domains, 1):
            print(f"      {i:2d}. {d:30s}  len={ln:>3s}  BL={bl:>6s}  reg={reg:>3s}  status={st}")
        sys.stdout.flush()
        return [d for d, _, _, _, _ in raw_domains]
    except Exception as e:
        print(f"\n  >>> ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return []
    finally:
        scraper.stop()


results = {}
results["URL A (sort by length asc)"] = scrape_url_raw(URL_A, "URL A – Sort by Length Ascending (5-10 chars, no hyphens)")
results["URL B (sort by reg TLDs desc)"] = scrape_url_raw(URL_B, "URL B – Sort by Most Registered TLDs (min 5 backlinks)")
results["URL C (sort by pop desc)"] = scrape_url_raw(URL_C, "URL C – Sort by Domain Popularity Descending")

print(f"\n{'='*70}")
print("  SUMMARY – All domains from each URL")
print(f"{'='*70}")
for label, domains in results.items():
    print(f"\n  {label} ({len(domains)} domains)")
    print(f"  {'-'*50}")
    if domains:
        for i, d in enumerate(domains, 1):
            print(f"    {i:2d}. {d}")
    else:
        print("    (no results / failed)")
print()
