from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func, cast, String


class ProductRepository:
    def __init__(self, db: AsyncSession, Product, ProductSyncLog):
        self.db             = db
        self.Product        = Product
        self.ProductSyncLog = ProductSyncLog

    async def get_by_id(self, product_id, seller_id):
        return (await self.db.execute(
            select(self.Product).where(
                self.Product.id == product_id,
                self.Product.seller_id == seller_id
            )
        )).scalar_one_or_none()

    async def get_by_external_id(self, seller_id, external_id):
        return (await self.db.execute(
            select(self.Product).where(
                self.Product.seller_id == seller_id,
                self.Product.external_product_id == external_id
            )
        )).scalar_one_or_none()

    async def list(self, seller_id, search=None, category=None, status=None, page=1, limit=20):
        query = select(self.Product).where(self.Product.seller_id == seller_id)
        if search:
            query = query.where(or_(
                self.Product.name.ilike(f"%{search}%"),
                self.Product.description.ilike(f"%{search}%")
            ))
        if category:
            query = query.where(self.Product.category == category)
        if status:
            query = query.where(cast(self.Product.status, String) == status)
        total    = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        products = (await self.db.execute(query.offset((page - 1) * limit).limit(limit))).scalars().all()
        return total, products

    async def upsert(self, seller_id, ext_id, data: dict):
        existing = await self.get_by_external_id(seller_id, ext_id)
        if existing:
            existing.name        = data.get("name", existing.name)
            existing.description = data.get("description", existing.description)
            existing.price       = data.get("price", existing.price)
            existing.images      = data.get("images", existing.images)
            existing.stock       = data.get("stock", existing.stock)
            existing.category    = data.get("category", existing.category)
            existing.meta        = data
            return existing, False
        product = self.Product(
            seller_id=seller_id, external_product_id=ext_id,
            name=data.get("name", "Unnamed"), description=data.get("description"),
            price=data.get("price"), images=data.get("images", []),
            stock=data.get("stock", 0), category=data.get("category"), meta=data,
        )
        self.db.add(product)
        return product, True

    async def add_sync_log(self, seller_id, status: str, synced_count: int, error_msg: str | None = None):
        self.db.add(self.ProductSyncLog(
            seller_id=seller_id, status=status,
            synced_count=synced_count, error_msg=error_msg
        ))

    async def get_sync_logs(self, seller_id, page=1, limit=20):
        return (await self.db.execute(
            select(self.ProductSyncLog)
            .where(self.ProductSyncLog.seller_id == seller_id)
            .order_by(self.ProductSyncLog.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        )).scalars().all()
