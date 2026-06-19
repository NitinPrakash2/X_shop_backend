from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import cast, String
from datetime import datetime, timezone


class PublishRepository:
    def __init__(self, db: AsyncSession, PublishJob, PublishedPost=None):
        self.db            = db
        self.PublishJob    = PublishJob
        self.PublishedPost = PublishedPost

    async def create_job(self, seller_id, product_id, status="pending", scheduled_at=None):
        job = self.PublishJob(
            seller_id=seller_id, product_id=product_id,
            status=status, scheduled_at=scheduled_at
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_failed_jobs(self, seller_id):
        return (await self.db.execute(
            select(self.PublishJob).where(
                self.PublishJob.seller_id == seller_id,
                cast(self.PublishJob.status, String) == "failed"
            )
        )).scalars().all()

    async def list_jobs(self, seller_id, status=None, page=1, limit=20):
        query = select(self.PublishJob).where(self.PublishJob.seller_id == seller_id)
        if status:
            query = query.where(cast(self.PublishJob.status, String) == status)
        return (await self.db.execute(
            query.order_by(self.PublishJob.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        )).scalars().all()

    async def record_published_post(self, seller_id, product_id, job_id, x_post_id: str, tweet_text: str):
        if not self.PublishedPost:
            return
        self.db.add(self.PublishedPost(
            seller_id=seller_id, product_id=product_id,
            publish_job_id=job_id, x_post_id=x_post_id,
            tweet_text=tweet_text, published_at=datetime.now(timezone.utc)
        ))

    async def list_published_posts(self, seller_id, page=1, limit=20):
        if not self.PublishedPost:
            return []
        return (await self.db.execute(
            select(self.PublishedPost)
            .where(self.PublishedPost.seller_id == seller_id)
            .order_by(self.PublishedPost.published_at.desc())
            .offset((page - 1) * limit).limit(limit)
        )).scalars().all()
