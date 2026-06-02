import json
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_FILE = Path("data/cookies.json")

URLS_TO_TEST = [
    # Sort by demand (reg TLDs descending)
    "https://member.expireddomains.net/domains/expiredcom/?o=statustld_registered&r=d&fonlycharhost=1&ftlds[]=2&fadult=1&flimit=200",
    # Alphabetical with all good filters (already works)
    "https://member.expireddomains.net/domains/expiredcom/?o=domain&r=a&fonlycharhost=1&ftlds[]=2&fadult=1&flimit=200",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    if COOKIE_FILE.exists():
        cookies = json.loads(COOKIE_FILE.read_text())
        context.add_cookies(cookies)

    page = context.new_page()

    for url in URLS_TO_TEST:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        base1 = page.locator("table.base1")
        rows = base1.locator("tbody tr, tr").all()
        data_rows = sum(1 for r in rows if r.locator("td").count() >= 20)
        print(f"URL: {page.url[:100]}...")
        print(f"  Rows: {len(rows)}, Data rows: {data_rows}")
        if data_rows > 0:
            first_row = None
            for r in rows:
                if r.locator("td").count() >= 20:
                    first_row = r.locator("td").first.inner_text().strip()
                    break
            print(f"  First domain: {first_row}")

    browser.close()
