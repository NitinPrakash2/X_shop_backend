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


def _get_models():
    mod = sys.modules.get("xshop_idx")
    if mod is None:
        _path = os.path.join(os.path.dirname(__file__), "..", "..", "index.py")
        spec  = importlib.util.spec_from_file_location("xshop_idx", os.path.abspath(_path))
        mod   = importlib.util.module_from_spec(spec)
        sys.modules["xshop_idx"] = mod
        spec.loader.exec_module(mod)
    return mod


def _load_x_client():
    path = os.path.join(os.path.dirname(__file__), "..", "integrations", "x", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_x_client", os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_sync_task():
    path = os.path.join(os.path.dirname(__file__), "..", "tasks", "sync_products.py")
    spec = importlib.util.spec_from_file_location("xshop_task_sync", os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _track_job(SchedulerJob, job_name: str, status: str, started_at, error_msg=None, meta=None):
    async with _AsyncSession() as db:
        db.add(SchedulerJob(
            job_name=job_name, status=status,
            started_at=started_at, finished_at=datetime.now(timezone.utc),
            error_msg=error_msg, meta=meta
        ))
        await db.commit()


async def _process_single_job(job, db, x, PublishJob, XAccount, OAuthToken, Product, PublishedPost):
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
    tweet_text   = f"\U0001f6cd\ufe0f {p.name}\n\n{p.description or ''}\n\n\U0001f4b0 Price: {p.price}"[:280]
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
    mod = _get_models()
    PublishJob, XAccount, OAuthToken, Product, PublishedPost, SchedulerJob = (
        mod.PublishJob, mod.XAccount, mod.OAuthToken, mod.Product, mod.PublishedPost, mod.SchedulerJob
    )
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
                    processed += await _process_single_job(job, db, x, PublishJob, XAccount, OAuthToken, Product, PublishedPost)
                except (ValueError, KeyError, RuntimeError) as e:
                    job.status    = "failed"
                    job.error_msg = str(e)
                    logger.error(f"scheduled job {job.id} failed: {e}")

            await db.commit()
            await _track_job(SchedulerJob, "process_scheduled_posts", "success", started_at, meta={"processed": processed})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_process_scheduled_posts error: {e}")
            await _track_job(SchedulerJob, "process_scheduled_posts", "failed", started_at, error_msg=str(e))


async def _retry_single_job(job, db, x, PublishJob, XAccount, OAuthToken, Product, PublishedPost):
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
    tweet_text   = f"\U0001f6cd\ufe0f {p.name}\n\n{p.description or ''}\n\n\U0001f4b0 Price: {p.price}"[:280]
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
    mod = _get_models()
    PublishJob, XAccount, OAuthToken, Product, PublishedPost, SchedulerJob = (
        mod.PublishJob, mod.XAccount, mod.OAuthToken, mod.Product, mod.PublishedPost, mod.SchedulerJob
    )
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
                    retried += await _retry_single_job(job, db, x, PublishJob, XAccount, OAuthToken, Product, PublishedPost)
                except (ValueError, KeyError, RuntimeError) as e:
                    logger.error(f"retry job {job.id} failed: {e}")

            await db.commit()
            await _track_job(SchedulerJob, "retry_failed_posts", "success", started_at, meta={"retried": retried})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_retry_failed_posts error: {e}")
            await _track_job(SchedulerJob, "retry_failed_posts", "failed", started_at, error_msg=str(e))


async def _auto_sync_products():
    mod = _get_models()
    Seller, Product, ProductSyncLog, SchedulerJob = (
        mod.Seller, mod.Product, mod.ProductSyncLog, mod.SchedulerJob
    )
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
            await _track_job(SchedulerJob, "auto_sync_products", "success", started_at, meta={"total_synced": total_synced})
        except (ValueError, RuntimeError) as e:
            logger.error(f"_auto_sync_products error: {e}")
            await _track_job(SchedulerJob, "auto_sync_products", "failed", started_at, error_msg=str(e))


def start_scheduler():
    scheduler.add_job(_process_scheduled_posts, "interval", minutes=1,  id="process_scheduled_posts", replace_existing=True)
    scheduler.add_job(_retry_failed_posts,       "interval", minutes=30, id="retry_failed_posts",       replace_existing=True)
    scheduler.add_job(_auto_sync_products,       "interval", hours=6,   id="auto_sync_products",        replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started — process_scheduled_posts(1m), retry_failed_posts(30m), auto_sync_products(6h)")


def stop_scheduler():
    scheduler.shutdown()
