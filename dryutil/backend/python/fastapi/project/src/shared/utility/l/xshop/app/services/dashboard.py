from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, cast, String


async def get_dashboard(request: Request, db: AsyncSession, Seller, XAccount, Product, PublishJob, Order) -> JSONResponse:
    seller_id = request.state.user["id"]

    total_products  = (await db.execute(select(func.count()).select_from(Product).where(Product.seller_id == seller_id))).scalar()
    published_count = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "published"))).scalar()
    scheduled_count = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "scheduled"))).scalar()
    failed_count    = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "failed"))).scalar()
    total_orders    = (await db.execute(select(func.count()).select_from(Order).where(Order.seller_id == seller_id))).scalar()
    x_acc           = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()

    return JSONResponse({"status": "success", "output": {
        "total_products":  total_products,
        "published_posts": published_count,
        "scheduled_posts": scheduled_count,
        "failed_posts":    failed_count,
        "total_orders":    total_orders,
        "x_account": {
            "is_connected":      x_acc.is_connected      if x_acc is not None else False,
            "username":          x_acc.username          if x_acc is not None else None,
            "followers_count":   x_acc.followers_count   if x_acc is not None else 0,
            "following_count":   x_acc.following_count   if x_acc is not None else 0,
            "profile_image_url": x_acc.profile_image_url if x_acc is not None else None,
            "last_synced_at":    x_acc.last_synced_at.isoformat() if x_acc is not None and x_acc.last_synced_at is not None else None,
        }
    }})


async def get_orders(request: Request, db: AsyncSession, Order) -> JSONResponse:
    seller_id = request.state.user["id"]
    page      = int(request.query_params.get("page", 1))
    limit     = int(request.query_params.get("limit", 20))
    status    = request.query_params.get("status")

    query = select(Order).where(Order.seller_id == seller_id)
    if status:
        query = query.where(cast(Order.status, String) == status)
    orders = (await db.execute(
        query.order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )).scalars().all()

    total = (await db.execute(select(func.count()).select_from(
        select(Order).where(Order.seller_id == seller_id).subquery()
    ))).scalar()

    return JSONResponse({"status": "success", "output": {
        "total": total, "page": page, "limit": limit,
        "items": [
            {
                "id":             str(o.id),
                "product_id":     str(o.product_id),
                "customer_name":  o.customer_name,
                "customer_email": o.customer_email,
                "amount":         float(o.amount) if o.amount else None,
                "status":         o.status,
                "created_at":     o.created_at.isoformat(),
            } for o in orders
        ]
    }})


async def get_analytics(request: Request, db: AsyncSession, Product, PublishJob, Order, AnalyticsEvent) -> JSONResponse:
    seller_id = request.state.user["id"]

    total_products  = (await db.execute(select(func.count()).select_from(Product).where(Product.seller_id == seller_id))).scalar()
    active_products = (await db.execute(select(func.count()).select_from(Product).where(Product.seller_id == seller_id, cast(Product.status, String) == "active"))).scalar()
    total_published = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "published"))).scalar()
    total_scheduled = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "scheduled"))).scalar()
    total_failed    = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.seller_id == seller_id, cast(PublishJob.status, String) == "failed"))).scalar()
    total_orders    = (await db.execute(select(func.count()).select_from(Order).where(Order.seller_id == seller_id))).scalar()
    pending_orders  = (await db.execute(select(func.count()).select_from(Order).where(Order.seller_id == seller_id, cast(Order.status, String) == "pending"))).scalar()

    return JSONResponse({"status": "success", "output": {
        "products": {
            "total":  total_products,
            "active": active_products,
        },
        "publishing": {
            "published": total_published,
            "scheduled": total_scheduled,
            "failed":    total_failed,
        },
        "orders": {
            "total":   total_orders,
            "pending": pending_orders,
        },
    }})


async def track_event(db: AsyncSession, AnalyticsEvent, seller_id: str, event_type: str, payload: dict = None):
    """Helper to record an analytics event."""
    db.add(AnalyticsEvent(seller_id=seller_id, event_type=event_type, payload=payload or {}))
    await db.commit()
