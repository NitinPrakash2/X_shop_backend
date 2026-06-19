import os
import httpx

PRODUCT_API_URL   = os.getenv("PRODUCT_API_URL", "http://localhost:8000/client/api/i/ona/product_dir")
PRODUCT_API_TOKEN = os.getenv("PRODUCT_API_TOKEN", "")


async def fetch_product_list() -> list:
    headers = {"Content-Type": "application/json"}
    if PRODUCT_API_TOKEN:
        headers["Authorization"] = f"Bearer {PRODUCT_API_TOKEN}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            PRODUCT_API_URL,
            params={"typ": "get_product_list"},
            json={},
            headers=headers
        )
        if resp.status_code != 200:
            raise RuntimeError(f"product API error: {resp.status_code} — {resp.text}")
        data = resp.json()
        return data.get("output", data.get("products", data if isinstance(data, list) else []))