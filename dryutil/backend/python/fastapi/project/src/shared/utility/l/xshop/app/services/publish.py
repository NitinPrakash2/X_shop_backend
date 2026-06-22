import httpx
import importlib.util
import os as _os
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


def _load_publish_repo(db, PublishJob, PublishedPost=None):
    path = _os.path.join(_os.path.dirname(__file__), "..", "repositories", "publish_repo.py")
    spec = importlib.util.spec_from_file_location("xshop_publish_repo", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PublishRepository(db, PublishJob, PublishedPost)


def _load_x_client():
    path = _os.path.join(_os.path.dirname(__file__), "..", "integrations", "x", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_x_client", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _post_tweet(access_token: str, text: str) -> str:
    return await _load_x_client().post_tweet(access_token, text)


def _get_product_url(p) -> str:
    """Extract product page URL from product's meta data."""
    meta = p.meta or {}
    for key in ("url", "product_url", "link", "permalink", "product_link", "page_url", "website_url", "source_url", "slug"):
        val = meta.get(key)
        if val and isinstance(val, str) and val.startswith("http"):
            return val
    # If meta has a slug but no full URL, try to build one
    slug = meta.get("slug") or meta.get("handle")
    if slug and isinstance(slug, str):
        return f"https://example.com/product/{slug.lstrip('/')}"
    return ""


def _build_tweet_text(p, custom_text: str = "") -> str:
    """Build tweet text with product info + link."""
    if custom_text:
        return custom_text[:280]
    url = _get_product_url(p)
    text = f"🛍️ {p.name}"
    if p.description:
        text += f"\n\n{p.description[:200]}"
    if p.price:
        text += f"\n💰 ₹{float(p.price)}"
    if url:
        text += f"\n🔗 {url}"
    elif p.external_product_id:
        text += f"\n📦 ID: {p.external_product_id[:20]}"
    return text[:280]


async def _get_valid_token(token_row, db) -> str:
    return await _load_x_client().get_valid_token(token_row, db)


async def _get_seller_token(seller_id, db, XAccount, OAuthToken):
    x_acc = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc or not x_acc.is_connected:
        raise HTTPException(400, "x account not connected")
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if not token_row:
        raise HTTPException(400, "no oauth token")
    return await _get_valid_token(token_row, db)


async def publish_product(request: Request, body: dict, db: AsyncSession, Product, PublishJob, XAccount, OAuthToken, PublishedPost=None) -> JSONResponse:
    seller_id  = request.state.user["id"]
    product_id = body.get("product_id")
    if not product_id:
        raise HTTPException(422, "product_id required")

    p = (await db.execute(select(Product).where(Product.id == product_id, Product.seller_id == seller_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "product not found")

    access_token = await _get_seller_token(seller_id, db, XAccount, OAuthToken)
    tweet_text   = _build_tweet_text(p, body.get("text", ""))

    repo = _load_publish_repo(db, PublishJob, PublishedPost)
    job  = await repo.create_job(seller_id, product_id)

    try:
        job.x_post_id    = await _post_tweet(access_token, tweet_text)
        job.status       = "published"
        job.published_at = datetime.now(timezone.utc)
        await repo.record_published_post(seller_id, product_id, job.id, job.x_post_id, tweet_text)
    except Exception as e:
        job.status    = "failed"
        job.error_msg = str(e)
        await db.commit()
        raise HTTPException(400, str(e))

    await db.commit()
    return JSONResponse({"status": "success", "output": {
        "job_id":       str(job.id),
        "x_post_id":    job.x_post_id,
        "status":       job.status,
        "published_at": job.published_at.isoformat(),
    }})


async def publish_bulk(request: Request, body: dict, db: AsyncSession, Product, PublishJob, XAccount, OAuthToken, PublishedPost=None) -> JSONResponse:
    seller_id   = request.state.user["id"]
    product_ids = body.get("product_ids", [])
    if not product_ids or not isinstance(product_ids, list):
        raise HTTPException(422, "product_ids array required")

    access_token = await _get_seller_token(seller_id, db, XAccount, OAuthToken)
    repo         = _load_publish_repo(db, PublishJob, PublishedPost)
    results      = []

    for product_id in product_ids:
        p = (await db.execute(select(Product).where(Product.id == product_id, Product.seller_id == seller_id))).scalar_one_or_none()
        if not p:
            results.append({"product_id": product_id, "status": "failed", "error": "not found"})
            continue

        tweet_text = _build_tweet_text(p)
        job        = await repo.create_job(seller_id, product_id)
        try:
            job.x_post_id    = await _post_tweet(access_token, tweet_text)
            job.status       = "published"
            job.published_at = datetime.now(timezone.utc)
            await repo.record_published_post(seller_id, product_id, job.id, job.x_post_id, tweet_text)
            results.append({"product_id": product_id, "status": "published", "job_id": str(job.id), "x_post_id": job.x_post_id})
        except Exception as e:
            job.status    = "failed"
            job.error_msg = str(e)
            results.append({"product_id": product_id, "status": "failed", "error": str(e)})

    await db.commit()
    return JSONResponse({"status": "success", "output": results})


async def schedule_product(request: Request, body: dict, db: AsyncSession, Product, PublishJob) -> JSONResponse:
    seller_id    = request.state.user["id"]
    product_id   = body.get("product_id")
    scheduled_at = body.get("scheduled_at")
    if not product_id or not scheduled_at:
        raise HTTPException(422, "product_id and scheduled_at required")

    p = (await db.execute(select(Product).where(Product.id == product_id, Product.seller_id == seller_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "product not found")

    repo = _load_publish_repo(db, PublishJob)
    job  = await repo.create_job(seller_id, product_id, "scheduled", datetime.fromisoformat(scheduled_at))
    await db.commit()
    await db.refresh(job)
    return JSONResponse({"status": "success", "output": {
        "job_id":       str(job.id),
        "status":       job.status,
        "scheduled_at": job.scheduled_at.isoformat(),
    }}, status_code=201)


async def retry_failed_jobs(request: Request, db: AsyncSession, Product, PublishJob, XAccount, OAuthToken, PublishedPost=None) -> JSONResponse:
    seller_id    = request.state.user["id"]
    repo         = _load_publish_repo(db, PublishJob, PublishedPost)
    failed       = await repo.get_failed_jobs(seller_id)
    if not failed:
        return JSONResponse({"status": "success", "output": {"retried": 0}})

    access_token = await _get_seller_token(seller_id, db, XAccount, OAuthToken)
    retried      = 0

    for job in failed:
        p = (await db.execute(select(Product).where(Product.id == job.product_id))).scalar_one_or_none()
        if not p:
            continue
        tweet_text = _build_tweet_text(p)
        try:
            job.x_post_id    = await _post_tweet(access_token, tweet_text)
            job.status       = "published"
            job.published_at = datetime.now(timezone.utc)
            job.error_msg    = None
            await repo.record_published_post(seller_id, p.id, job.id, job.x_post_id, tweet_text)
            retried += 1
        except Exception as e:
            job.error_msg = str(e)

    await db.commit()
    return JSONResponse({"status": "success", "output": {"retried": retried}})


async def get_publish_jobs(request: Request, body: dict, db: AsyncSession, PublishJob) -> JSONResponse:
    seller_id = request.state.user["id"]
    repo      = _load_publish_repo(db, PublishJob)
    jobs      = await repo.list_jobs(
        seller_id,
        status = body.get("status") or request.query_params.get("status"),
        page   = int(body.get("page") or request.query_params.get("page", 1)),
        limit  = int(body.get("limit") or request.query_params.get("limit", 20)),
    )
    return JSONResponse({"status": "success", "output": [
        {
            "id":           str(j.id),
            "product_id":   str(j.product_id),
            "x_post_id":    j.x_post_id,
            "status":       j.status.value if hasattr(j.status, "value") else j.status,
            "scheduled_at": j.scheduled_at.isoformat() if j.scheduled_at else None,
            "published_at": j.published_at.isoformat() if j.published_at else None,
            "error_msg":    j.error_msg,
            "created_at":   j.created_at.isoformat(),
        } for j in jobs
    ]})


async def get_published_posts(request: Request, body: dict, db: AsyncSession, PublishedPost) -> JSONResponse:
    seller_id = request.state.user["id"]
    repo      = _load_publish_repo(db, None, PublishedPost)
    posts     = await repo.list_published_posts(
        seller_id,
        page  = int(body.get("page") or request.query_params.get("page", 1)),
        limit = int(body.get("limit") or request.query_params.get("limit", 20)),
    )
    return JSONResponse({"status": "success", "output": [
        {
            "id":           str(p.id),
            "product_id":   str(p.product_id),
            "x_post_id":    p.x_post_id,
            "tweet_text":   p.tweet_text,
            "published_at": p.published_at.isoformat() if p.published_at else None,
        } for p in posts
    ]})
