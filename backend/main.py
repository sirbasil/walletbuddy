from fastapi import FastAPI
from scraper import scrape_amazon, scrape_flipkart, compare_all_stores

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Backend running 🚀"}

@app.get("/scrape")
def scrape(url: str):
    if "amazon" in url:
        return scrape_amazon(url)
    elif "flipkart" in url:
        return scrape_flipkart(url)
    else:
        return {"error": "Unsupported site"}

@app.get("/compare")
def compare(url: str):
    return compare_all_stores(url)