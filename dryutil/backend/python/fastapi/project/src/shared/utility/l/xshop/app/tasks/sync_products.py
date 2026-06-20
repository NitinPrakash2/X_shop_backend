"""
tasks/sync_products.py

Reusable product sync task — called by:
  - sync_products API action (manual)
  - scheduler _auto_sync_products (scheduled, every 6h)
  - x_oauth_callback (auto-trigger after OAuth)

Synchronizes products from external API into PostgreSQL database.
"""
import importlib.util
import os as _os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _load_product_api_client():
    path = _os.path.join(_os.path.dirname(__file__), "..", "integrations", "product_api", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_product_api", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run_product_sync(seller_id, db, Product, ProductSyncLog, query: str = "", page: int = 1, per_page: int = 100) -> dict:
    """
    Fetches products from external API and upserts into DB for given seller.
    
    Returns: {
        "success": bool,
        "received": int,
        "created": int,
        "updated": int,
        "failed": int,
        "message": str
    }
    
    Logs activity to ProductSyncLog.
    """
    sync_start_time = datetime.now(timezone.utc)
    api = _load_product_api_client()
    
    created = updated = failed = 0
    error_details = []
    
    try:
        logger.info(f"Starting product sync for seller {seller_id}")
        
        # Fetch from external API - get all products
        result = await api.fetch_product_list(query=query, page=page, per_page=per_page)
        
        if not result["success"]:
            error_msg = result.get("error", "Unknown API error")
            logger.error(f"Product API failed: {error_msg}")
            
            db.add(ProductSyncLog(
                seller_id=seller_id,
                status="failed",
                synced_count=0,
                error_msg=error_msg
            ))
            await db.commit()
            
            return {
                "success": False,
                "received": 0,
                "created": 0,
                "updated": 0,
                "failed": 0,
                "message": f"API Error: {error_msg}"
            }
        
        products_data = result.get("data", [])
        total_received = len(products_data)
        
        logger.info(f"Received {total_received} products from API")
        
        if total_received == 0:
            logger.warning(f"No products received for seller {seller_id}")
            db.add(ProductSyncLog(
                seller_id=seller_id,
                status="success",
                synced_count=0,
                error_msg=None
            ))
            await db.commit()
            return {
                "success": True,
                "received": 0,
                "created": 0,
                "updated": 0,
                "failed": 0,
                "message": "No products received"
            }
        
        # Process each product
        from sqlalchemy.future import select
        
        for idx, p in enumerate(products_data):
            try:
                # Extract external product ID
                ext_id = str(p.get("id") or p.get("external_id") or p.get("_id") or p.get("product_id") or "")
                
                if not ext_id or ext_id == "None":
                    logger.warning(f"Product {idx} has no valid ID, skipping")
                    error_details.append(f"Product {idx}: Missing ID")
                    failed += 1
                    continue
                
                # Check if product already exists
                existing = (await db.execute(
                    select(Product).where(
                        Product.seller_id == seller_id,
                        Product.external_product_id == ext_id
                    )
                )).scalar_one_or_none()
                
                # Prepare product fields - extract from various possible fields
                name = p.get("name") or p.get("title") or p.get("slug") or p.get("brand") or "Unnamed Product"
                description = p.get("description") or p.get("desc") or ""
                price = p.get("price") or p.get("cost") or None
                images = p.get("images") or p.get("image") or []
                stock = p.get("stock") or p.get("inventory") or p.get("quantity") or 0
                category = p.get("category") or p.get("cat") or ""
                status = p.get("status") or "active"
                
                # Handle category as list
                if isinstance(category, list):
                    category = " ".join(str(c) for c in category) if category else ""
                
                # Convert price to float if string
                if isinstance(price, str):
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        price = None
                
                # Convert stock to int if string
                if isinstance(stock, str):
                    try:
                        stock = int(stock)
                    except (ValueError, TypeError):
                        stock = 0
                
                logger.info(f"Processing product: {name} (ID: {ext_id})")
                
                if existing:
                    # UPDATE existing product
                    existing.name = name
                    existing.description = description
                    existing.price = price
                    existing.images = images if isinstance(images, list) else [images]
                    existing.stock = stock
                    existing.category = category
                    existing.status = status
                    existing.meta = p  # Store full metadata
                    db.add(existing)
                    updated += 1
                    logger.debug(f"Updated product {ext_id}")
                
                else:
                    # CREATE new product
                    import uuid
                    new_product = Product(
                        id=uuid.uuid4(),
                        seller_id=seller_id,
                        external_product_id=ext_id,
                        name=name,
                        description=description,
                        price=price,
                        images=images if isinstance(images, list) else [images],
                        stock=stock,
                        category=category,
                        status=status,
                        meta=p  # Store full API response as metadata
                    )
                    db.add(new_product)
                    created += 1
                    logger.debug(f"Created product {ext_id}")
            
            except Exception as e:
                logger.error(f"Error processing product {idx}: {str(e)}")
                error_details.append(f"Product {idx}: {str(e)}")
                failed += 1
                continue
        
        # Commit all changes
        await db.commit()
        logger.info(f"Sync completed: {created} created, {updated} updated, {failed} failed out of {total_received}")
        
        # Log sync result
        db.add(ProductSyncLog(
            seller_id=seller_id,
            status="success",
            synced_count=created + updated,
            error_msg="; ".join(error_details) if error_details else None
        ))
        await db.commit()
        
        return {
            "success": True,
            "received": total_received,
            "created": created,
            "updated": updated,
            "failed": failed,
            "message": f"Synced {total_received} products: {created} created, {updated} updated, {failed} failed"
        }
    
    except Exception as e:
        error_msg = f"Sync error: {str(e)}"
        logger.error(error_msg)
        
        try:
            db.add(ProductSyncLog(
                seller_id=seller_id,
                status="failed",
                synced_count=0,
                error_msg=error_msg
            ))
            await db.commit()
        except:
            pass  # Don't crash if logging fails
        
        return {
            "success": False,
            "received": 0,
            "created": created,
            "updated": updated,
            "failed": failed,
            "message": error_msg
        }
