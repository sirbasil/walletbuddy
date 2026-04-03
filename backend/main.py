from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scraper import compare_all_stores
from supabase import create_client
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import statistics

load_dotenv()

app = FastAPI()

# ======================
# CORS
# ======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# SUPABASE
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# HELPERS
# ======================

def detect_site(url: str):
    if "amazon" in url:
        return "amazon"
    elif "flipkart" in url:
        return "flipkart"
    elif "croma" in url:
        return "croma"
    elif "reliancedigital" in url or "reliance" in url:
        return "reliance"
    return None


def extract_price(value):
    if value is None:
        return None

    # already number → return directly
    if isinstance(value, (int, float)):
        return int(value)

    try:
        return int(str(value).replace(",", "").replace("₹", "").strip())
    except:
        return None

def is_cache_valid(last_fetched):
    last = datetime.fromisoformat(last_fetched)
    return datetime.utcnow() - last < timedelta(hours=24)

# ======================
# ROUTES
# ======================

@app.get("/")
def home():
    return {"message": "pricewatch backend running 🚀"}


@app.get("/compare")
def compare(url: str):
    return compare_all_stores(url)


# ======================
# MAIN TRACK API
# ======================

@app.post("/track")
def track(payload: dict):
    url = payload.get("url")
    days = payload.get("days", 30)

    if not url:
        return {"error": "No URL provided"}

    site = detect_site(url)
    if not site:
        return {"error": "Unsupported site"}

    stores_data = None
    source = {}

    # ======================
    # STEP 1: CHECK CACHE
    # ======================
    existing = supabase.table("products") \
        .select("*") \
        .eq("url", url) \
        .execute()

    if existing.data:
        product = existing.data[0]
        product_id = product["id"]

        # ======================
        # STEP 2: REFRESH IF NEEDED
        # ======================
        if not product.get("current_price") or not is_cache_valid(product["last_fetched"]):
            stores_data = compare_all_stores(url)
            source = stores_data.get(site, {})

            raw_price = source.get("price")
            price = extract_price(raw_price)

            supabase.table("products").update({
                "current_price": price,
                "last_fetched": datetime.utcnow().isoformat(),
                "name": source.get("name", product.get("name")),
                "image_url": source.get("image", product.get("image_url")),
            }).eq("id", product_id).execute()

            if price:
                supabase.table("price_history").insert({
                    "product_id": product_id,
                    "price": price
                }).execute()

    else:
        # ======================
        # STEP 3: FIRST SCRAPE
        # ======================
        stores_data = compare_all_stores(url)
        source = stores_data.get(site, {})

        raw_price = source.get("price")
        price = extract_price(raw_price)

        result = supabase.table("products").insert({
            "url": url,
            "name": source.get("name", ""),
            "image_url": source.get("image", ""),
            "current_price": price,
            "site": site,
            "last_fetched": datetime.utcnow().isoformat()
        }).execute()

        product = result.data[0]
        product_id = product["id"]

        if price:
            supabase.table("price_history").insert({
                "product_id": product_id,
                "price": price
            }).execute()

    # ======================
    # STEP 4: FETCH HISTORY
    # ======================
    history = supabase.table("price_history") \
        .select("*") \
        .eq("product_id", product_id) \
        .order("scraped_at") \
        .execute()

    # ======================
    # STEP 5: STORE COMPARISON (OPTIMIZED)
    # ======================
    if not stores_data:
        stores_data = compare_all_stores(url)

    stores_result = []

    for store_name in ["amazon", "flipkart", "croma", "reliance"]:
        s = stores_data.get(store_name)

        # ONLY VALID DATA
        price = extract_price(s.get("price"))

        if s and not s.get("error") and price:
            stores_result.append({
            "store": store_name,
            "price": price,
            "url": s.get("url", "")
            })

    # ======================
    # STEP 6: PREDICTION
    # ======================
    prices = [h["price"] for h in history.data if h["price"]]

    if prices:
        current = prices[-1]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0

        # simple trend logic
        if current <= min_price * 1.03:
            verdict = "buy now"
        elif current > avg_price + std_dev:
            verdict = "wait"
        else:
            verdict = "neutral"

        confidence = min(95, int(70 + (std_dev / avg_price) * 100 if avg_price else 80))

    else:
        verdict = "unknown"
        confidence = 50
        min_price = None
        max_price = None

    prediction = {
        "verdict": verdict,
        "confidence": confidence,
        "lowest_ever": min_price,
        "highest_ever": max_price,
    }

    # ======================
    # FINAL RESPONSE
    # ======================
    return {
        "product": product,
        "history": history.data,
        "stores": stores_result,
        "prediction": prediction
    }