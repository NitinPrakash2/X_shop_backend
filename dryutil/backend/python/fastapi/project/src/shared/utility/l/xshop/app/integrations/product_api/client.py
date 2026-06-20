import os
import httpx
import logging

logger = logging.getLogger(__name__)

PRODUCT_API_URL   = os.getenv("PRODUCT_API_URL", "http://localhost:8000/client/api/i/ona/product_dir")
PRODUCT_API_TOKEN = os.getenv("PRODUCT_API_TOKEN", "")


async def fetch_product_list(query: str = "", page: int = 1, per_page: int = 100):
    """
    Fetch products from external API.
    
    Returns: {
        "success": bool,
        "data": [products],
        "total": int,
        "page": int,
        "error": str (if failed)
    }
    """
    headers = {
        "Content-Type": "application/json",
        "lang-code": "en"
    }
    if PRODUCT_API_TOKEN:
        headers["Authorization"] = f"Bearer {PRODUCT_API_TOKEN}"
    
    payload = {
        "q": query,
        "page": page,
        "per_page": per_page
    }
    
    try:
        logger.info(f"Fetching products from {PRODUCT_API_URL} with query={query}, page={page}, per_page={per_page}")
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                PRODUCT_API_URL,
                params={"typ": "get_product_list"},
                json=payload,
                headers=headers
            )
            
            logger.info(f"Product API response status: {resp.status_code}")
            
            if resp.status_code != 200:
                error_msg = f"Product API error: {resp.status_code} - {resp.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "data": [],
                    "error": error_msg
                }
            
            data = resp.json()
            logger.info(f"Product API response keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
            
            # Parse response - handle different formats
            products = []
            total = 0
            
            if isinstance(data, dict):
                # Format 1: {\"success\": true, \"data\": {\"products\": [...], \"found\": N}}
                if data.get("success") and "data" in data:
                    data_obj = data["data"]
                    if isinstance(data_obj, dict):
                        products = data_obj.get("products", [])
                        total = data_obj.get("found", len(products))
                    else:
                        products = [data_obj]
                        total = 1
                # Format 2: {\"status\": \"success\", \"output\": [...]}
                elif data.get("status") == "success" and "output" in data:
                    products = data["output"] if isinstance(data["output"], list) else [data["output"]]
                    total = len(products)
                # Format 3: {\"products\": [...], \"total\": N}
                elif "products" in data:
                    products = data["products"] if isinstance(data["products"], list) else [data["products"]]
                    total = data.get("total", len(products))
                # Format 4: {\"data\": [...]}
                elif "data" in data:
                    products = data["data"] if isinstance(data["data"], list) else [data["data"]]
                    total = data.get("total", len(products))
                # Format 5: Direct list
                elif isinstance(data, list):
                    products = data
                    total = len(products)
                # Format 6: Top-level keys indicate products
                else:
                    products = [data]
                    total = 1
            elif isinstance(data, list):
                products = data
                total = len(products)
            
            logger.info(f"Parsed {len(products)} products from API response (total: {total})")
            
            return {
                "success": True,
                "data": products,
                "total": total,
                "page": page,
                "per_page": per_page
            }
    
    except httpx.TimeoutException:
        error_msg = f"Product API timeout after 30 seconds"
        logger.error(error_msg)
        return {"success": False, "data": [], "error": error_msg}
    
    except httpx.RequestError as e:
        error_msg = f"Product API request error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "data": [], "error": error_msg}
    
    except ValueError as e:
        error_msg = f"Product API invalid JSON: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "data": [], "error": error_msg}
    
    except Exception as e:
        error_msg = f"Product API unexpected error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "data": [], "error": error_msg}
