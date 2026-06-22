"""
tasks/sync_products.py

Reusable product sync task — called by:
  - sync_products API action (manual)
  - scheduler _auto_sync_products (scheduled, every 6h)
  - x_oauth_callback (auto-trigger after OAuth)

Synchronizes products from external API into PostgreSQL database with improved field mapping.
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
    
    Improved field extraction:
    - Name: slug (which includes brand prefix)
    - Price: variant_prices[0] > variant_mrp[0] > price field
    - Stock: variant_stock_idx[0] > stock field
    - Images: url field or images array
    - Brand: extracted separately for metadata
    - Category: joined array to string
    
    Returns: {
        "success": bool,
        "received": int,
        "created": int,
        "updated": int,
        "failed": int,
        "message": str,
        "data_issues": dict
    }
    """
    sync_start_time = datetime.now(timezone.utc)
    api = _load_product_api_client()
    
    created = updated = failed = 0
    error_details = []
    data_issues = {
        "missing_price": 0,
        "missing_stock": 0,
        "missing_images": 0,
        "missing_category": 0
    }
    
    try:
        logger.info(f"Starting product sync for seller {seller_id}")
        
        # Fetch from external API
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
                "message": f"API Error: {error_msg}",
                "data_issues": {}
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
                "message": "No products received",
                "data_issues": {}
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
                
                # EXTRACT: Product Name (use slug which includes brand prefix)
                name = p.get("slug") or p.get("title") or p.get("name") or p.get("brand") or "Unnamed Product"
                
                # EXTRACT: Description
                description = p.get("description") or p.get("desc") or ""
                
                # EXTRACT: Brand (for metadata and potential future field)
                brand = p.get("brand") or ""
                
                # EXTRACT: Price from variant_prices array, fallback to variant_mrp or price field
                price = None
                price_source = None
                
                variant_prices = p.get("variant_prices", [])
                if isinstance(variant_prices, list) and len(variant_prices) > 0:
                    try:
                        # Use first variant price
                        price_val = variant_prices[0]
                        if price_val and price_val > 0:
                            price = float(price_val)
                            price_source = "variant_prices"
                    except (ValueError, TypeError):
                        pass
                
                if price is None:
                    variant_mrp = p.get("variant_mrp", [])
                    if isinstance(variant_mrp, list) and len(variant_mrp) > 0:
                        try:
                            price_val = variant_mrp[0]
                            if price_val and price_val > 0:
                                price = float(price_val)
                                price_source = "variant_mrp"
                        except (ValueError, TypeError):
                            pass
                
                if price is None:
                    try:
                        price = float(p.get("price") or p.get("cost") or 0)
                        if price <= 0:
                            price = None
                        else:
                            price_source = "price_field"
                    except (ValueError, TypeError):
                        price = None
                
                if price is None:
                    data_issues["missing_price"] += 1
                
                # EXTRACT: Images from common API response fields
                images = []
                img_sources = [
                    p.get("url"),
                    p.get("image_url"), p.get("img_url"),
                    p.get("image"), p.get("img"),
                    p.get("thumbnail"), p.get("thumbnail_url"),
                    p.get("picture"), p.get("picture_url"),
                    p.get("photo"), p.get("photos"),
                    p.get("media_url"), p.get("media"),
                    p.get("imageSrc"), p.get("src"),
                    p.get("main_image"), p.get("featured_image"),
                    p.get("display_image"), p.get("primary_image"),
                ]
                img_arrays = [
                    p.get("images"), p.get("image_urls"), p.get("img_urls"),
                    p.get("pictures"), p.get("photos"), p.get("media_urls"),
                    p.get("gallery"), p.get("all_images"),
                ]
                for src in img_sources:
                    if src and isinstance(src, str) and src.strip():
                        images = [src.strip()]
                        break
                if not images:
                    for arr in img_arrays:
                        if arr and isinstance(arr, list) and len(arr) > 0:
                            valid = [i for i in arr if isinstance(i, str) and i.strip()]
                            if valid:
                                images = valid
                                break
                
                if not images:
                    data_issues["missing_images"] += 1
                
                # EXTRACT: Stock from variant_stock_idx array or stock field
                stock = 0
                stock_source = None
                
                variant_stock = p.get("variant_stock_idx", [])
                if isinstance(variant_stock, list) and len(variant_stock) > 0:
                    try:
                        stock_val = variant_stock[0]
                        if stock_val:
                            stock = int(stock_val)
                            stock_source = "variant_stock_idx"
                    except (ValueError, TypeError):
                        pass
                
                if stock == 0:
                    stock_val = p.get("stock") or p.get("inventory") or p.get("quantity")
                    if isinstance(stock_val, str):
                        try:
                            stock = int(stock_val)
                            stock_source = "stock_field"
                        except (ValueError, TypeError):
                            stock = 0
                    elif isinstance(stock_val, int) and stock_val > 0:
                        stock = stock_val
                        stock_source = "stock_field"
                
                if stock == 0:
                    data_issues["missing_stock"] += 1
                
                # EXTRACT: Category as joined string from array
                category = ""
                cat_raw = p.get("category") or p.get("cat") or []
                if isinstance(cat_raw, list):
                    category = " ".join(str(c) for c in cat_raw) if cat_raw else ""
                else:
                    category = str(cat_raw) if cat_raw else ""
                
                if not category:
                    data_issues["missing_category"] += 1
                
                # EXTRACT: Status
                status = p.get("status") or "active"
                
                logger.info(f"Processing product: {name} (ID: {ext_id}, price_src: {price_source}, stock_src: {stock_source})")
                
                if existing:
                    # UPDATE existing product
                    existing.name = name
                    existing.description = description
                    existing.price = price
                    existing.images = images if isinstance(images, list) else [images]
                    existing.stock = stock
                    existing.category = category
                    existing.status = status
                    existing.meta = p  # Store full API response as metadata
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
            "message": f"Synced {total_received} products: {created} created, {updated} updated, {failed} failed",
            "data_issues": data_issues
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
            pass
        
        return {
            "success": False,
            "received": 0,
            "created": created,
            "updated": updated,
            "failed": failed,
            "message": error_msg,
            "data_issues": data_issues
        }
