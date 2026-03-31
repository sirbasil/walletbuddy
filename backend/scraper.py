from playwright.sync_api import sync_playwright


# -------------------------
# AMAZON SCRAPER
# -------------------------
def scrape_amazon(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # NAME
        try:
            page.wait_for_selector("#productTitle", timeout=10000)
            name = page.locator("#productTitle").inner_text().strip()
        except:
            name = page.title()

        # PRICE
        try:
            price = page.locator(".a-price-whole").first.inner_text().strip()
            price = price.replace(",", "").replace(".", "")
        except:
            price = "Not found"

        # IMAGE
        try:
            image = page.locator("#landingImage").get_attribute("src")
        except:
            image = "Not found"

        browser.close()

        return {
            "site": "amazon",
            "name": name,
            "price": price,
            "image": image
        }


# -------------------------
# FLIPKART SCRAPER
# -------------------------
def scrape_flipkart(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Close login popup if exists
        try:
            page.locator("button._2KpZ6l._2doB4z").click(timeout=3000)
        except:
            pass

        # NAME
        try:
            name = page.locator("span.B_NuCI").inner_text().strip()
        except:
            name = page.title()

        # PRICE
        try:
            price = page.locator("div._30jeq3._16Jk6d").inner_text().strip()
            price = price.replace("₹", "").replace(",", "")
        except:
            price = "Not found"

        # IMAGE
        try:
            image = page.locator("img._396cs4").first.get_attribute("src")
        except:
            image = "Not found"

        browser.close()

        return {
            "site": "flipkart",
            "name": name,
            "price": price,
            "image": image
        }