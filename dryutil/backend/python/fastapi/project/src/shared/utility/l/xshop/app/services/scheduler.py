import os
import sys
import logging
import importlib.util
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import cast, String

logger        = logging.getLogger(__name__)
scheduler     = AsyncIOScheduler()
DATABASE_URL  = os.getenv("DATABASE_URL", "")
_engine       = create_async_engine(DATABASE_URL, echo=False)
_AsyncSession = sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

# Direct imports from xshop module
from src.shared.utility.l.xshop.index import (
    Seller, SellerProfile, Store, XAccount, OAuthToken, Product, 
    ProductSyncLog, PublishJob, Order, AnalyticsEvent, 
    SellerRefreshToken, PublishedPost, SchedulerJob
)

_x_client_cache = None
_sync_task_cache = None


def _load_x_client():
    global _x_client_cache
    if _x_client_cache is not None:
        return _x_client_cache
    
    path = os.path.join(os.path.dirname(__file__), "..", "integrations", "x", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_x_client", os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    _x_client_cache = mod
    return _x_client_cache


def _load_sync_task():
    global _sync_task_cache
    if _sync_task_cache is not None:
        return _sync_task_cache
    
    path = os.path.join(os.path.dirname(__file__), "..", "tasks", "sync_products.py")
    spec = importlib.util.spec_from_file_location("xshop_task_sync", os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    _sync_task_cache = mod
    return _sync_task_cache


async def _track_job(job_name: str, status: str, started_at, error_msg=None, meta=None):
    async with _AsyncSession() as db:
        db.add(SchedulerJob(
            job_name=job_name, status=status,
            started_at=started_at, finished_at=datetime.now(timezone.utc),
            error_msg=error_msg, meta=meta
        ))
        await db.commit()


async def _process_single_job(job, db, x):
    """Process a single scheduled job."""
    x_acc = (await db.execute(select(XAccount).where(XAccount.seller_id == job.seller_id))).scalar_one_or_none()
    if x_acc is None or not x_acc.is_connected:
        return 0
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if token_row is None:
        return 0
    p = (await db.execute(select(Product).where(Product.id == job.product_id))).scalar_one_or_none()
    if p is None:
        return 0

    access_token = await x.get_valid_token(token_row, db)
    tweet_text   = f"🛍️ {p.name}\n\n{p.description or ''}\n\n💰 Price: {p.price}"[:280]
    post_id      = await x.post_tweet(access_token, tweet_text)

    job.status       = "published"
    job.x_post_id    = post_id
    job.published_at = datetime.now(timezone.utc)
    db.add(PublishedPost(
        seller_id=job.seller_id, product_id=job.product_id,
        publish_job_id=job.id, x_post_id=post_id,
        tweet_text=tweet_text, published_at=job.published_at
    ))
    return 1


async def _process_scheduled_posts():
    started_at = datetime.now(timezone.utc)
    x          = _load_x_client()

    async with _AsyncSession() as db:
        try:
            now  = datetime.now(timezone.utc)
            jobs = (await db.execute(
                select(PublishJob).where(
                    cast(PublishJob.status, String) == "scheduled",
                    PublishJob.scheduled_at <= now
                )
            )).scalars().all()

            processed = 0
            for job in jobs:
                try:
                    processed += await _process_single_job(job, db, x)
                except (ValueError, KeyError, RuntimeError) as e:
                    job.status    = "failed"
                    job.error_msg = str(e)
                    logger.error(f"scheduled job {job.id} failed: {e}")

            await db.commit()
            await _track_job("process_scheduled_posts", "success", started_at, meta={"processed": processed})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_process_scheduled_posts error: {e}")
            await _track_job("process_scheduled_posts", "failed", started_at, error_msg=str(e))


async def _retry_single_job(job, db, x):
    """Retry a single failed job."""
    x_acc = (await db.execute(select(XAccount).where(XAccount.seller_id == job.seller_id))).scalar_one_or_none()
    if x_acc is None or not x_acc.is_connected:
        return 0
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if token_row is None:
        return 0
    p = (await db.execute(select(Product).where(Product.id == job.product_id))).scalar_one_or_none()
    if p is None:
        return 0

    access_token = await x.get_valid_token(token_row, db)
    tweet_text   = f"🛍️ {p.name}\n\n{p.description or ''}\n\n💰 Price: {p.price}"[:280]
    post_id      = await x.post_tweet(access_token, tweet_text)

    job.status       = "published"
    job.x_post_id    = post_id
    job.published_at = datetime.now(timezone.utc)
    job.error_msg    = None
    db.add(PublishedPost(
        seller_id=job.seller_id, product_id=job.product_id,
        publish_job_id=job.id, x_post_id=post_id,
        tweet_text=tweet_text, published_at=job.published_at
    ))
    return 1


async def _retry_failed_posts():
    started_at = datetime.now(timezone.utc)
    x          = _load_x_client()

    async with _AsyncSession() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            jobs   = (await db.execute(
                select(PublishJob).where(
                    cast(PublishJob.status, String) == "failed",
                    PublishJob.created_at >= cutoff
                )
            )).scalars().all()

            retried = 0
            for job in jobs:
                try:
                    retried += await _retry_single_job(job, db, x)
                except (ValueError, KeyError, RuntimeError) as e:
                    logger.error(f"retry job {job.id} failed: {e}")

            await db.commit()
            await _track_job("retry_failed_posts", "success", started_at, meta={"retried": retried})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_retry_failed_posts error: {e}")
            await _track_job("retry_failed_posts", "failed", started_at, error_msg=str(e))


async def _auto_sync_products():
    started_at = datetime.now(timezone.utc)
    task       = _load_sync_task()

    async with _AsyncSession() as db:
        try:
            sellers      = (await db.execute(select(Seller).where(Seller.is_active is True))).scalars().all()
            total_synced = 0
            for seller in sellers:
                try:
                    result = await task.run_product_sync(str(seller.id), db, Product, ProductSyncLog)
                    total_synced += result.get("synced", 0)
                except (ValueError, RuntimeError, KeyError) as e:
                    logger.error(f"auto sync seller {seller.id} failed: {e}")
            await _track_job("auto_sync_products", "success", started_at, meta={"total_synced": total_synced})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_auto_sync_products error: {e}")
            await _track_job("auto_sync_products", "failed", started_at, error_msg=str(e))


def start_scheduler():
    scheduler.add_job(_process_scheduled_posts, "interval", minutes=1,  id="process_scheduled_posts", replace_existing=True)
    scheduler.add_job(_retry_failed_posts,       "interval", minutes=30, id="retry_failed_posts",       replace_existing=True)
    scheduler.add_job(_auto_sync_products,       "interval", hours=6,   id="auto_sync_products",        replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started — process_scheduled_posts(1m), retry_failed_posts(30m), auto_sync_products(6h)")


def stop_scheduler():
    scheduler.shutdown()
