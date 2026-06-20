from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


class SellerRepository:
    def __init__(self, db: AsyncSession, Seller, SellerProfile):
        self.db           = db
        self.Seller       = Seller
        self.SellerProfile = SellerProfile

    async def get_by_email(self, email: str):
        return (await self.db.execute(
            select(self.Seller).where(self.Seller.email == email)
        )).scalar_one_or_none()

    async def get_by_id(self, seller_id):
        return (await self.db.execute(
            select(self.Seller).where(self.Seller.id == seller_id)
        )).scalar_one_or_none()

    async def create(self, email: str, password_hash: str):
        seller = self.Seller(email=email, password_hash=password_hash)
        self.db.add(seller)
        await self.db.flush()
        return seller

    async def create_profile(self, seller_id, full_name: str | None = None):
        profile = self.SellerProfile(seller_id=seller_id, full_name=full_name)
        self.db.add(profile)

    async def get_profile(self, seller_id):
        return (await self.db.execute(
            select(self.SellerProfile).where(self.SellerProfile.seller_id == seller_id)
        )).scalar_one_or_none()

    async def save_refresh_token(self, SellerRefreshToken, seller_id, token_hash: str, expires_at):
        existing = (await self.db.execute(
            select(SellerRefreshToken).where(SellerRefreshToken.seller_id == seller_id)
        )).scalar_one_or_none()
        if existing:
            existing.token_hash = token_hash
            existing.expires_at = expires_at
            existing.is_revoked = False
        else:
            self.db.add(SellerRefreshToken(
                seller_id=seller_id, token_hash=token_hash, expires_at=expires_at
            ))
        await self.db.commit()

    async def get_refresh_token(self, SellerRefreshToken, seller_id):
        return (await self.db.execute(
            select(SellerRefreshToken).where(
                SellerRefreshToken.seller_id == seller_id,
                SellerRefreshToken.is_revoked is False
            )
        )).scalar_one_or_none()

    async def revoke_refresh_token(self, SellerRefreshToken, seller_id):
        row = await self.get_refresh_token(SellerRefreshToken, seller_id)
        if row:
            row.is_revoked = True
            await self.db.commit()
