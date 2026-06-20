from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey
from src.db_config import Base
import uuid


class XAccount(Base):
    __tablename__ = "xshop_x_account"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True)
    x_user_id = Column(String, nullable=True, index=True)
    username = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    profile_image_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    is_connected = Column(Boolean, default=False, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    account_meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("Seller", back_populates="x_account")
    oauth_token = relationship("OAuthToken", back_populates="x_account", uselist=False, cascade="all, delete")


class OAuthToken(Base):
    __tablename__ = "xshop_oauth_token"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    x_account_id = Column(UUID(as_uuid=True), ForeignKey("xshop_x_account.id", ondelete="CASCADE"), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    scope = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    x_account = relationship("XAccount", back_populates="oauth_token")
