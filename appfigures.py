import os
import json
import requests
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Appfigures API helpers ---

APPFIGURES_API_BASE = 'https://api.appfigures.com/v2'
PAT = os.environ.get('APPFIGURES_PAT')

def make_request_bearer(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Make a GET request to Appfigures API using Bearer token auth."""
    if not PAT:
        raise ValueError("APPFIGURES_PAT environment variable not set")
    url = f"{APPFIGURES_API_BASE}{endpoint}"
    headers = {
        'Authorization': f'Bearer {PAT}',
        'Content-Type': 'application/json'
    }
    logger.info(f"Making request to {url} with params {params}")
    response = requests.get(url, headers=headers, params=params)
    if not response.ok:
        try:
            error_details = response.json()
            error_msg = f"API Error: {response.status_code} - {error_details.get('message', '')}"
        except Exception:
            error_msg = f"API Error: {response.status_code} - {response.text}"
        raise Exception(error_msg)
    data = response.json()
    logger.info(f"Response type: {type(data)}")
    logger.info(f"Response sample: {json.dumps(data)[:200]}...")
    return data

def fetch_appfigures_data() -> Dict[str, Any]:
    """
    Fetches products, sales, usage, and ratings from Appfigures and combines them.
    Returns a dict keyed by product ID.
    """
    try:
        # Step 1: Get products
        logger.info("Fetching products...")
        products = make_request_bearer('/products/mine', {'store': 'apple'})
        logger.info(f"Products response type: {type(products)}")
        logger.info(f"Products keys: {products.keys() if isinstance(products, dict) else 'Not a dict'}")
        
        product_ids = ','.join(str(pid) for pid in products.keys())
        if not product_ids:
            raise Exception("No products found.")
            
        # Step 2: Get sales
        logger.info("Fetching sales...")
        sales = make_request_bearer('/reports/sales', {'group_by': 'product', 'products': product_ids})
        logger.info(f"Sales response type: {type(sales)}")
        
        # Step 3: Get usage
        logger.info("Fetching usage...")
        usage = make_request_bearer('/reports/usage', {
            'group_by': 'product',
            'products': product_ids,
            'usage_type': 'app_store_views,impressions',
            'storefront': 'apple'
        })
        logger.info(f"Usage response type: {type(usage)}")
        
        # Step 4: Get ratings
        logger.info("Fetching ratings...")
        ratings = make_request_bearer('/ratings', {'products': product_ids})
        logger.info(f"Ratings response type: {type(ratings)}")
        
        # Step 5: Combine all data
        combined = {}
        for pid in products.keys():
            combined[pid] = {
                "product": products[pid],
                "sales": sales.get(pid, {}) if isinstance(sales, dict) else {},
                "usage": usage.get(pid, {}) if isinstance(usage, dict) else {},
                "ratings": ratings.get(pid, {}) if isinstance(ratings, dict) else {}
            }
        return combined
    except Exception as e:
        logger.error(f"Error in fetch_appfigures_data: {str(e)}", exc_info=True)
        raise

# --- FastAPI setup ---

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to the Appfigures Data API! Use /appfigures-data to get your app data."}

@app.get("/appfigures-data")
def get_appfigures_data():
    try:
        data = fetch_appfigures_data()
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CLI/debug usage ---

def test_endpoints():
    """Test multiple endpoints with different auth methods (debug only)."""
    endpoints = [
        '/products',
        '/products/mine?store=apple',
        '/reports/sales',
        '/users/info'
    ]
    results = {}
    print("\n=== Testing with Bearer Token Auth ===")
    for endpoint in endpoints:
        print(f"\nTrying endpoint: {endpoint}")
        try:
            make_request_bearer(endpoint, None)
            results[f"bearer_{endpoint}"] = "Success"
            print("Success!")
        except Exception as e:
            results[f"bearer_{endpoint}"] = f"Failed: {str(e)}"
            print(f"Failed: {e}")
    return results

if __name__ == "__main__":
    try:
        print("PAT first 5 chars:", PAT[:5] + "..." if PAT else "Not set")
        # Debug: test endpoints
        # results = test_endpoints()
        # print("\n=== Summary of Results ===")
        # for endpoint, result in results.items():
        #     print(f"{endpoint}: {result}")

        # CLI: fetch and print all app data
        data = fetch_appfigures_data()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")