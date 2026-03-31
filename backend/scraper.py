from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from difflib import SequenceMatcher
import re
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# -------------------------
# SIMILARITY FUNCTION
# -------------------------
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# -------------------------
# GENERIC KEYWORD EXTRACTOR
# -------------------------
def extract_keywords(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    words = name.split()

    stopwords = {
        "with", "and", "for", "the", "this", "that",
        "inch", "cm", "mm", "new", "latest", "best",
        "pack", "combo", "set", "buy", "online", "india",
        "free", "delivery", "product", "original",
        "laptop", "mobile", "phone", "price", "offer",
        "sale", "discount", "off", "only", "just"
    }

    seen = set()
    keywords = []
    for w in words:
        if w not in stopwords and w not in seen and len(w) > 1:
            seen.add(w)
            keywords.append(w)

    return " ".join(keywords[:8])


def extract_features(name):
    name = name.lower()

    features = {
        "brand": None,
        "cpu": None,
        "ram": None,
        "storage": None
    }

    # BRAND
    brands = ["hp", "dell", "lenovo", "asus", "acer", "apple"]
    for b in brands:
        if b in name:
            features["brand"] = b
            break

    # CPU
    if "ryzen 5" in name:
        features["cpu"] = "ryzen5"
    elif "ryzen 7" in name:
        features["cpu"] = "ryzen7"
    elif "i5" in name:
        features["cpu"] = "i5"
    elif "i7" in name:
        features["cpu"] = "i7"

    # RAM
    ram_match = re.search(r"(\d+)\s?gb", name)
    if ram_match:
        features["ram"] = ram_match.group(1)

    # STORAGE
    storage_match = re.search(r"(\d+)\s?(gb|tb)", name)
    if storage_match:
        features["storage"] = storage_match.group(1) + storage_match.group(2)

    return features

def feature_score(f1, f2):
    score = 0

    # weights
    weights = {
        "brand": 0.2,
        "cpu": 0.4,
        "ram": 0.2,
        "storage": 0.2
    }

    for key in weights:
        if f1.get(key) and f2.get(key):
            if f1[key] == f2[key]:
                score += weights[key]

    return score

# -------------------------
# PRICE CLEANER
# -------------------------
def clean_price(raw):
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    try:
        return float(cleaned)
    except ValueError:
        return None


# -------------------------
# AMAZON SCRAPER
# -------------------------
def scrape_amazon(url, page):
    log.info(f"Scraping Amazon: {url}")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # NAME — multiple fallback selectors
    name = None
    for selector in ["#productTitle", "h1.a-size-large", "h1[data-automation-id='title']", "h1"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=5000)
            name = el.inner_text().strip()
            if name:
                break
        except Exception:
            continue
    if not name:
        name = page.title()

    # PRICE — multiple fallback selectors
    price_raw = None
    for selector in [
        ".a-price-whole",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".a-price .a-offscreen",
        "span[data-a-color='price'] .a-offscreen"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            price_raw = el.inner_text().strip()
            if price_raw:
                break
        except Exception:
            continue

    # RATING — multiple fallback selectors
    rating = None
    for selector in [
        "#acrPopover",
        "span[data-hook='rating-out-of-text']",
        ".a-icon-alt"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            rating_text = el.inner_text().strip() or el.get_attribute("title") or ""
            match = re.search(r"(\d+\.?\d*)\s*out of", rating_text)
            if match:
                rating = float(match.group(1))
                break
        except Exception:
            continue

    # IMAGE
    image = None
    for selector in ["#landingImage", "#imgTagWrapperId img", "#main-image"]:
        try:
            el = page.locator(selector).first
            image = el.get_attribute("src") or el.get_attribute("data-old-hires")
            if image:
                break
        except Exception:
            continue

    return {
        "site": "amazon",
        "name": name,
        "price": clean_price(price_raw),
        "price_raw": price_raw,
        "image": image,
        "rating": rating,
        "url": url
    }


# -------------------------
# FLIPKART SCRAPER
# -------------------------
def scrape_flipkart(url, page):
    log.info(f"Scraping Flipkart: {url}")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # Close login popup
    for selector in ["button._2KpZ6l._2doB4z", "button[class*='_2doB4z']", "._2AkmmA button"]:
        try:
            page.locator(selector).click(timeout=2000)
            break
        except Exception:
            continue

    # NAME — multiple fallbacks
    name = None
    for selector in [
        "span.B_NuCI",
        "h1.yhB1nd",
        "h1[class*='product-title']",
        ".x-product-title",
        "h1"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=5000)
            name = el.inner_text().strip()
            if name:
                break
        except Exception:
            continue
    if not name:
        name = page.title()

    # PRICE — multiple fallbacks
    price_raw = None
    for selector in [
        "div._30jeq3._16Jk6d",
        "div._30jeq3",
        "div[class*='_16Jk6d']",
        "._25b18 ._30jeq3",
        "div[class*='price']"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            price_raw = el.inner_text().strip()
            if price_raw:
                break
        except Exception:
            continue

    # RATING
    rating = None
    for selector in [
        "div._3LWZlK",
        "div[class*='rating'] span",
        "._2d4LTz"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            rating_text = el.inner_text().strip()
            rating = float(rating_text)
            break
        except Exception:
            continue

    # IMAGE
    image = None
    for selector in ["img._396cs4", "img._2r_T1I", "img[class*='product-image']", "._2r_T1I img"]:
        try:
            el = page.locator(selector).first
            image = el.get_attribute("src")
            if image:
                break
        except Exception:
            continue

    return {
        "site": "flipkart",
        "name": name,
        "price": clean_price(price_raw),
        "price_raw": price_raw,
        "image": image,
        "rating": rating,
        "url": url
    }


# -------------------------
# CROMA SCRAPER
# -------------------------
def scrape_croma(url, page):
    log.info(f"Scraping Croma: {url}")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    name = None
    for selector in ["h1.pd-title", "h1[class*='product']", "h1"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=5000)
            name = el.inner_text().strip()
            if name:
                break
        except Exception:
            continue
    if not name:
        name = page.title()

    price_raw = None
    for selector in ["span.pdp-selling-price", ".new-price", "span[class*='selling-price']"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            price_raw = el.inner_text().strip()
            if price_raw:
                break
        except Exception:
            continue

    rating = None
    for selector in [".rating-count", "span[class*='rating']"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            rating_text = el.inner_text().strip()
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                rating = float(match.group(1))
                break
        except Exception:
            continue

    image = None
    for selector in [".product-img img", "img[class*='product']", ".pdp-image img"]:
        try:
            el = page.locator(selector).first
            image = el.get_attribute("src")
            if image:
                break
        except Exception:
            continue

    return {
        "site": "croma",
        "name": name,
        "price": clean_price(price_raw),
        "price_raw": price_raw,
        "image": image,
        "rating": rating,
        "url": url
    }


# -------------------------
# RELIANCE DIGITAL SCRAPER
# -------------------------
def scrape_reliance(url, page):
    log.info(f"Scraping Reliance Digital: {url}")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    name = None
    for selector in ["h1.pdp__title", "h1[class*='title']", "h1"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=5000)
            name = el.inner_text().strip()
            if name:
                break
        except Exception:
            continue
    if not name:
        name = page.title()

    price_raw = None
    for selector in [
        "span.pdp__offerPrice",
        ".price__offer",
        "span[class*='offerPrice']",
        "span[class*='price']"
    ]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            price_raw = el.inner_text().strip()
            if price_raw:
                break
        except Exception:
            continue

    rating = None
    for selector in [".rating__count", "span[class*='rating']"]:
        try:
            el = page.locator(selector).first
            el.wait_for(timeout=3000)
            rating_text = el.inner_text().strip()
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                rating = float(match.group(1))
                break
        except Exception:
            continue

    image = None
    for selector in [".pdp__image img", "img[class*='product']"]:
        try:
            el = page.locator(selector).first
            image = el.get_attribute("src")
            if image:
                break
        except Exception:
            continue

    return {
        "site": "reliance",
        "name": name,
        "price": clean_price(price_raw),
        "price_raw": price_raw,
        "image": image,
        "rating": rating,
        "url": url
    }


# -------------------------
# SEARCH FLIPKART
# -------------------------
def search_flipkart_links(query, page, max_results=5):
    log.info(f"Searching Flipkart for: {query}")
    links = []

    search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    try:
        page.wait_for_selector("a[href*='/p/']", timeout=10000)
        elements = page.locator("a[href*='/p/']").all()
        seen = set()
        for el in elements:
            try:
                href = el.get_attribute("href")
                if href and "/p/" in href:
                    full = "https://www.flipkart.com" + href.split("?")[0]
                    if full not in seen:
                        seen.add(full)
                        links.append(full)
                if len(links) >= max_results:
                    break
            except Exception:
                continue
    except Exception as e:
        log.warning(f"Flipkart search failed: {e}")

    return links


# -------------------------
# SEARCH CROMA
# -------------------------
def search_croma_links(query, page, max_results=3):
    log.info(f"Searching Croma for: {query}")
    links = []

    search_url = f"https://www.croma.com/searchB?q={query.replace(' ', '%20')}"
    page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    try:
        elements = page.locator("a[href*='/p/']").all()
        seen = set()
        for el in elements[:max_results]:
            href = el.get_attribute("href")
            if href:
                full = "https://www.croma.com" + href if href.startswith("/") else href
                if full not in seen:
                    seen.add(full)
                    links.append(full)
    except Exception as e:
        log.warning(f"Croma search failed: {e}")

    return links


# -------------------------
# SEARCH RELIANCE DIGITAL
# -------------------------
def search_reliance_links(query, page, max_results=3):
    log.info(f"Searching Reliance Digital for: {query}")
    links = []

    search_url = f"https://www.reliancedigital.in/search?q={query.replace(' ', '%20')}"
    page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    try:
        elements = page.locator("a[href*='/p/']").all()
        seen = set()
        for el in elements[:max_results]:
            href = el.get_attribute("href")
            if href:
                full = "https://www.reliancedigital.in" + href if href.startswith("/") else href
                if full not in seen:
                    seen.add(full)
                    links.append(full)
    except Exception as e:
        log.warning(f"Reliance Digital search failed: {e}")

    return links


# -------------------------
# FIND BEST MATCH
# -------------------------
def find_best_match(original_name, candidates, threshold=0.5):
    best = None
    best_score = 0

    f1 = extract_features(original_name)

    for data in candidates:
        if not data.get("name"):
            continue

        f2 = extract_features(data["name"])

        # combine both scores
        sim = similarity(original_name, data["name"])
        feat = feature_score(f1, f2)

        total_score = 0.5 * sim + 0.5 * feat

        log.info(f"Score {total_score:.2f} (sim={sim:.2f}, feat={feat:.2f})")

        if total_score > best_score:
            best_score = total_score
            best = data

    if best_score < threshold:
        return None, best_score

    best["match_score"] = round(best_score, 3)
    return best, best_score
# -------------------------
# DETECT STORE FROM URL
# -------------------------
def detect_store(url):
    url = url.lower()
    if "amazon" in url:
        return "amazon"
    if "flipkart" in url:
        return "flipkart"
    if "croma" in url:
        return "croma"
    if "reliancedigital" in url:
        return "reliance"
    return None


# -------------------------
# MAIN COMPARE FUNCTION
# -------------------------
def compare_all_stores(url):
    """
    Given any product URL from Amazon, Flipkart, Croma, or Reliance Digital,
    scrape the source product and then find & compare it across all other stores.
    Returns a dict with results from all 4 stores.
    """
    results = {
        "amazon": None,
        "flipkart": None,
        "croma": None,
        "reliance": None,
        "source_store": None,
        "product_name": None,
        "product_image": None,
        "product_rating": None
    }

    source_store = detect_store(url)
    results["source_store"] = source_store

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        # --- Scrape source product ---
        try:
            if source_store == "amazon":
                source_data = scrape_amazon(url, page)
            elif source_store == "flipkart":
                source_data = scrape_flipkart(url, page)
            elif source_store == "croma":
                source_data = scrape_croma(url, page)
            elif source_store == "reliance":
                source_data = scrape_reliance(url, page)
            else:
                browser.close()
                return {"error": "Unsupported store URL"}

            results[source_store] = source_data
            product_name = source_data["name"]
            results["product_name"] = product_name
            results["product_image"] = source_data.get("image")
            results["product_rating"] = source_data.get("rating")

            search_query = extract_keywords(product_name)
            log.info(f"Search query: {search_query}")

        except Exception as e:
            log.error(f"Failed to scrape source URL: {e}")
            browser.close()
            return {"error": str(e)}

        # --- Search and scrape other stores ---

        # FLIPKART
        if source_store != "flipkart":
            try:
                fk_links = search_flipkart_links(search_query, page)
                fk_candidates = []
                for link in fk_links[:3]:
                    try:
                        data = scrape_flipkart(link, page)
                        fk_candidates.append(data)
                    except Exception as e:
                        log.warning(f"Flipkart scrape failed for {link}: {e}")
                best, score = find_best_match(product_name, fk_candidates)
                results["flipkart"] = best or {"error": "no match found", "best_score": score}
            except Exception as e:
                log.error(f"Flipkart comparison failed: {e}")
                results["flipkart"] = {"error": str(e)}

        # CROMA
        if source_store != "croma":
            try:
                croma_links = search_croma_links(search_query, page)
                croma_candidates = []
                for link in croma_links[:2]:
                    try:
                        data = scrape_croma(link, page)
                        croma_candidates.append(data)
                    except Exception as e:
                        log.warning(f"Croma scrape failed for {link}: {e}")
                best, score = find_best_match(product_name, croma_candidates)
                results["croma"] = best or {"error": "no match found", "best_score": score}
            except Exception as e:
                log.error(f"Croma comparison failed: {e}")
                results["croma"] = {"error": str(e)}

        # RELIANCE
        if source_store != "reliance":
            try:
                rel_links = search_reliance_links(search_query, page)
                rel_candidates = []
                for link in rel_links[:2]:
                    try:
                        data = scrape_reliance(link, page)
                        rel_candidates.append(data)
                    except Exception as e:
                        log.warning(f"Reliance scrape failed for {link}: {e}")
                best, score = find_best_match(product_name, rel_candidates)
                results["reliance"] = best or {"error": "no match found", "best_score": score}
            except Exception as e:
                log.error(f"Reliance comparison failed: {e}")
                results["reliance"] = {"error": str(e)}

        # AMAZON
        if source_store != "amazon":
            try:
                search_url = f"https://www.amazon.in/s?k={search_query.replace(' ', '+')}"
                page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                amz_links = []
                elements = page.locator("a[href*='/dp/']").all()
                seen = set()
                for el in elements[:3]:
                    href = el.get_attribute("href")
                    if href and "/dp/" in href:
                        full = "https://www.amazon.in" + href if href.startswith("/") else href
                        full = full.split("?")[0]
                        if full not in seen:
                            seen.add(full)
                            amz_links.append(full)

                amz_candidates = []
                for link in amz_links[:2]:
                    try:
                        data = scrape_amazon(link, page)
                        amz_candidates.append(data)
                    except Exception as e:
                        log.warning(f"Amazon scrape failed for {link}: {e}")

                best, score = find_best_match(product_name, amz_candidates)
                results["amazon"] = best or {"error": "no match found", "best_score": score}

            except Exception as e:
                log.error(f"Amazon comparison failed: {e}")
                results["amazon"] = {"error": str(e)}

        browser.close()

    return results


