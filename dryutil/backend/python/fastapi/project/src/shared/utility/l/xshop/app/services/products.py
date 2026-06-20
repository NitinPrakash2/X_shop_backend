import importlib.util
import os as _os
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _load_repo(db, Product, ProductSyncLog):
    path = _os.path.join(_os.path.dirname(__file__), "..", "repositories", "product_repo.py")
    spec = importlib.util.spec_from_file_location("xshop_product_repo", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ProductRepository(db, Product, ProductSyncLog)


def _load_sync_task():
    path = _os.path.join(_os.path.dirname(__file__), "..", "tasks", "sync_products.py")
    spec = importlib.util.spec_from_file_location("xshop_task_sync", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def sync_products(request: Request, db: AsyncSession, Product, ProductSyncLog) -> JSONResponse:
    """
    Manual product sync endpoint.
    Fetches products from external API and syncs them.
    """
    seller_id = request.state.user["id"]
    
    try:
        query = request.query_params.get("query", "")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 100))
        
        logger.info(f"Syncing products for seller {seller_id} with query={query}")
        
        result = await _load_sync_task().run_product_sync(seller_id, db, Product, ProductSyncLog, query=query, page=page, per_page=per_page)
        
        if result["success"]:
            return JSONResponse({
                "status": "success",
                "output": {
                    "received": result["received"],
                    "created": result["created"],
                    "updated": result["updated"],
                    "failed": result["failed"],
                    "message": result["message"]
                }
            })
        else:
            raise HTTPException(400, result["message"])
    
    except ValueError as e:
        logger.error(f"Sync error: {str(e)}")
        raise HTTPException(400, f"sync failed: {str(e)}")
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        raise HTTPException(400, f"sync failed: {str(e)}")


async def get_sync_logs(request: Request, db: AsyncSession, ProductSyncLog) -> JSONResponse:
    """Get product sync history for seller."""
    seller_id = request.state.user["id"]
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 20))
    
    from sqlalchemy.future import select
    logs = (await db.execute(
        select(ProductSyncLog).where(ProductSyncLog.seller_id == seller_id)
        .order_by(ProductSyncLog.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    )).scalars().all()
    
    return JSONResponse({
        "status": "success",
        "output": [
            {
                "id": str(l.id),
                "status": l.status,
                "synced_count": l.synced_count,
                "error_msg": l.error_msg,
                "created_at": l.created_at.isoformat(),
            } for l in logs
        ]
    })


async def get_products(request: Request, db: AsyncSession, Product, ProductSyncLog) -> JSONResponse:
    """Get products for seller with real API data."""
    seller_id = request.state.user["id"]
    repo = _load_repo(db, Product, ProductSyncLog)
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 20))
    
    total, products = await repo.list(
        seller_id,
        search = request.query_params.get("search"),
        category = request.query_params.get("category"),
        status = request.query_params.get("status"),
        page=page, limit=limit,
    )
    
    return JSONResponse({
        "status": "success",
        "output": {
            "total": total, "page": page, "limit": limit,
            "items": [
                {
                    "id": str(p.id),
                    "external_product_id": p.external_product_id,
                    "name": p.name,
                    "description": p.description,
                    "price": float(p.price) if p.price else None,
                    "images": p.images or [],
                    "stock": p.stock,
                    "category": p.category,
                    "status": p.status,
                } for p in products
            ]
        }
    })


async def get_product(request: Request, body: dict, db: AsyncSession, Product, ProductSyncLog) -> JSONResponse:
    """Get single product details with real API data."""
    seller_id = request.state.user["id"]
    product_id = body.get("product_id") or request.query_params.get("product_id")
    
    if not product_id:
        raise HTTPException(422, "product_id required")
    
    repo = _load_repo(db, Product, ProductSyncLog)
    p = await repo.get_by_id(product_id, seller_id)
    
    if not p:
        raise HTTPException(404, "product not found")
    
    return JSONResponse({
        "status": "success",
        "output": {
            "id": str(p.id),
            "external_product_id": p.external_product_id,
            "name": p.name,
            "description": p.description,
            "price": float(p.price) if p.price else None,
            "images": p.images or [],
            "stock": p.stock,
            "category": p.category,
            "status": p.status,
            "meta": p.meta,  # Full metadata from API
        }
    })
