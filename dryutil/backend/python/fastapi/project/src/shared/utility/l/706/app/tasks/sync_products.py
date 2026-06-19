"""
tasks/sync_products.py
Reusable product sync task — called by:
  - sync_products API action (manual)
  - scheduler _auto_sync_products (scheduled, every 6h)
  - x_oauth_callback (auto-trigger after OAuth)
"""
import importlib.util
import os as _os


def _load_product_api_client():
    path = _os.path.join(_os.path.dirname(__file__), "..", "integrations", "product_api", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_product_api", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run_product_sync(seller_id, db, Product, ProductSyncLog) -> dict:
    """
    Fetches products from external API and upserts into DB for given seller.
    Returns {"synced": int, "updated": int} or raises on failure.
    Logs result to ProductSyncLog.
    """
    api = _load_product_api_client()
    synced = updated = 0
    try:
        products = await api.fetch_product_list()
        for p in products:
            ext_id = str(p.get("id") or p.get("external_id") or p.get("_id") or "")
            if not ext_id:
                continue
            from sqlalchemy.future import select
            existing = (await db.execute(
                select(Product).where(
                    Product.seller_id == seller_id,
                    Product.external_product_id == ext_id
                )
            )).scalar_one_or_none()
            if existing:
                existing.name        = p.get("name", existing.name)
                existing.description = p.get("description", existing.description)
                existing.price       = p.get("price", existing.price)
                existing.images      = p.get("images", existing.images)
                existing.stock       = p.get("stock", existing.stock)
                existing.category    = p.get("category", existing.category)
                existing.meta        = p
                updated += 1
            else:
                db.add(Product(
                    seller_id=seller_id, external_product_id=ext_id,
                    name=p.get("name", "Unnamed"), description=p.get("description"),
                    price=p.get("price"), images=p.get("images", []),
                    stock=p.get("stock", 0), category=p.get("category"), meta=p,
                ))
                synced += 1
        await db.commit()
        db.add(ProductSyncLog(seller_id=seller_id, status="success", synced_count=synced + updated))
        await db.commit()
        return {"synced": synced, "updated": updated}
    except Exception as e:
        db.add(ProductSyncLog(seller_id=seller_id, status="failed", synced_count=0, error_msg=str(e)))
        await db.commit()
        raise
