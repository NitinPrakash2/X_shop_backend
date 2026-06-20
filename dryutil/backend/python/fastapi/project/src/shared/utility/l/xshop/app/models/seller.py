from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db_config import Base
import uuid


class Seller(Base):
    __tablename__ = "xshop_seller"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # relationships
    profile = relationship("SellerProfile", back_populates="seller", uselist=False, cascade="all, delete")
    store = relationship("Store", back_populates="seller", uselist=False, cascade="all, delete")
    x_account = relationship("XAccount", back_populates="seller", uselist=False, cascade="all, delete")
    products = relationship("Product", back_populates="seller", cascade="all, delete")
    publish_jobs = relationship("PublishJob", back_populates="seller", cascade="all, delete")
    orders = relationship("Order", back_populates="seller", cascade="all, delete")


class SellerProfile(Base):
    __tablename__ = "xshop_seller_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), __import__('sqlalchemy').ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("Seller", back_populates="profile")
