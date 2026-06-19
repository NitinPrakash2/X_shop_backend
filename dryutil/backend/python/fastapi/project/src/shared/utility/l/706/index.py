import importlib
import os
from typing import Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, relationship
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, JSON, ForeignKey, Numeric, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.db_config import Base, engine
from src.shared.util.include_file.index import include_file
from src.database.entity.instance import Instance
from src.database.entity.project import Project
import uuid
import enum


# ============================================================
# ENUMS
# ============================================================

class PublishStatus(str, enum.Enum):
    pending   = "pending"
    published = "published"
    failed    = "failed"
    scheduled = "scheduled"

class ProductStatus(str, enum.Enum):
    active   = "active"
    inactive = "inactive"

class OrderStatus(str, enum.Enum):
    pending   = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"

class SyncStatus(str, enum.Enum):
    success = "success"
    failed  = "failed"


# ============================================================
# MODELS
# ============================================================

class Seller(Base):
    __tablename__ = "xshop_seller"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile      = relationship("SellerProfile", back_populates="seller", uselist=False, cascade="all, delete")
    store        = relationship("Store",         back_populates="seller", uselist=False, cascade="all, delete")
    x_account    = relationship("XAccount",      back_populates="seller", uselist=False, cascade="all, delete")
    products     = relationship("Product",       back_populates="seller", cascade="all, delete")
    publish_jobs = relationship("PublishJob",    back_populates="seller", cascade="all, delete")
    orders       = relationship("Order",         back_populates="seller", cascade="all, delete")


class SellerProfile(Base):
    __tablename__ = "xshop_seller_profile"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id  = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name  = Column(String, nullable=True)
    phone      = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("Seller", back_populates="profile")


class Store(Base):
    __tablename__  = "xshop_store"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id      = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True)
    name           = Column(String, nullable=False)
    description    = Column(Text, nullable=True)
    logo_url       = Column(String, nullable=True)
    banner_url     = Column(String, nullable=True)
    contact_email  = Column(String, nullable=True)
    support_number = Column(String, nullable=True)
    website_url    = Column(String, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("Seller", back_populates="store")


class XAccount(Base):
    __tablename__     = "xshop_x_account"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id         = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True)
    x_user_id         = Column(String, nullable=True, index=True)
    username          = Column(String, nullable=True)
    display_name      = Column(String, nullable=True)
    profile_image_url = Column(String, nullable=True)
    bio               = Column(Text, nullable=True)
    followers_count   = Column(Integer, default=0)
    following_count   = Column(Integer, default=0)
    is_connected      = Column(Boolean, default=False, nullable=False)
    last_synced_at    = Column(DateTime(timezone=True), nullable=True)
    account_meta      = Column(JSON, nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller      = relationship("Seller",     back_populates="x_account")
    oauth_token = relationship("OAuthToken", back_populates="x_account", uselist=False, cascade="all, delete")


class OAuthToken(Base):
    __tablename__ = "xshop_oauth_token"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    x_account_id  = Column(UUID(as_uuid=True), ForeignKey("xshop_x_account.id", ondelete="CASCADE"), nullable=False, unique=True)
    access_token  = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry  = Column(DateTime(timezone=True), nullable=True)
    scope         = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    x_account = relationship("XAccount", back_populates="oauth_token")


class Product(Base):
    __tablename__       = "xshop_product"
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id           = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    external_product_id = Column(String, nullable=False, index=True)
    name                = Column(String, nullable=False)
    description         = Column(Text, nullable=True)
    price               = Column(Numeric(10, 2), nullable=True)
    images              = Column(JSON, nullable=True)
    stock               = Column(Integer, default=0)
    category            = Column(String, nullable=True)
    status              = Column(String, default="active", nullable=False)
    meta                = Column(JSON, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller       = relationship("Seller",     back_populates="products")
    publish_jobs = relationship("PublishJob", back_populates="product",  cascade="all, delete")


class ProductSyncLog(Base):
    __tablename__ = "xshop_product_sync_log"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    status        = Column(String, nullable=False)
    synced_count  = Column(Integer, default=0)
    error_msg     = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublishJob(Base):
    __tablename__ = "xshop_publish_job"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id    = Column(UUID(as_uuid=True), ForeignKey("xshop_product.id", ondelete="CASCADE"), nullable=False, index=True)
    x_post_id     = Column(String, nullable=True)
    status        = Column(String, default="pending", nullable=False)
    scheduled_at  = Column(DateTime(timezone=True), nullable=True)
    published_at  = Column(DateTime(timezone=True), nullable=True)
    error_msg     = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller  = relationship("Seller",  back_populates="publish_jobs")
    product = relationship("Product", back_populates="publish_jobs")


class Order(Base):
    __tablename__  = "xshop_order"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id      = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_product.id", ondelete="CASCADE"), nullable=False)
    customer_name  = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    amount         = Column(Numeric(10, 2), nullable=True)
    status         = Column(String, default="pending", nullable=False)
    meta           = Column(JSON, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("Seller", back_populates="orders")


class AnalyticsEvent(Base):
    __tablename__ = "xshop_analytics_event"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type    = Column(String, nullable=False)
    payload       = Column(JSON, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SellerRefreshToken(Base):
    __tablename__ = "xshop_seller_refresh_token"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token_hash    = Column(String, nullable=False)
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    is_revoked    = Column(Boolean, default=False, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PublishedPost(Base):
    __tablename__  = "xshop_published_post"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id      = Column(UUID(as_uuid=True), ForeignKey("xshop_seller.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id     = Column(UUID(as_uuid=True), ForeignKey("xshop_product.id", ondelete="CASCADE"), nullable=False, index=True)
    publish_job_id = Column(UUID(as_uuid=True), ForeignKey("xshop_publish_job.id", ondelete="SET NULL"), nullable=True)
    x_post_id      = Column(String, nullable=False, index=True)
    tweet_text     = Column(Text, nullable=True)
    published_at   = Column(DateTime(timezone=True), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SchedulerJob(Base):
    __tablename__ = "xshop_scheduler_job"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name      = Column(String, nullable=False, index=True)
    status        = Column(String, nullable=False, default="running")  # running | success | failed
    started_at    = Column(DateTime(timezone=True), nullable=False)
    finished_at   = Column(DateTime(timezone=True), nullable=True)
    error_msg     = Column(Text, nullable=True)
    meta          = Column(JSON, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ============================================================
# SERVICE LOADER  (avoids invalid module name with leading digit)
# ============================================================

_BASE = os.path.dirname(__file__)

def _load_service(name: str):
    # Validate service name - only alphanumeric and underscore to prevent path injection
    if not name.replace('_', '').isalnum():
        raise ValueError(f"Invalid service name: {name}")
    
    path = os.path.join(_BASE, "app", "services", f"{name}.py")
    # Resolve to absolute path and validate it's within expected directory
    abs_path = os.path.abspath(path)
    expected_base = os.path.abspath(os.path.join(_BASE, "app", "services"))
    if not abs_path.startswith(expected_base):
        raise ValueError(f"Path traversal attempt detected: {abs_path}")
    
    spec = importlib.util.spec_from_file_location(f"xshop_svc_{name}", abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load service: {name}")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_auth      = _load_service("auth")
_store     = _load_service("store")
_x_account = _load_service("x_account")
_products  = _load_service("products")
_publish   = _load_service("publish")
_dashboard = _load_service("dashboard")


# ============================================================
# PUBLIC ACTIONS  (no auth required)
# ============================================================

_PUBLIC_ACTIONS = {"register", "login", "refresh_token", "x_oauth_callback"}


# ============================================================
# UTILITY INDEX
# ============================================================

async def index(_p={'data': Any}):

    async def i(request: Request, params: dict, db: AsyncSession):
        try:
            body   = await request.json() if await request.body() else {}
            action = body.get("action") or request.query_params.get("action") or ""

            # ---- Auth ----
            if action == "register":
                return await _auth.register(body, db, Seller, SellerProfile, SellerRefreshToken)
            if action == "login":
                return await _auth.login(body, db, Seller, SellerRefreshToken)
            if action == "refresh_token":
                return await _auth.refresh_token(body, db, Seller, SellerRefreshToken)
            if action == "logout":
                return await _auth.logout(request, db, SellerRefreshToken)
            if action == "me":
                return await _auth.me(request, db, Seller, SellerProfile)
            if action == "update_profile":
                return await _auth.update_profile(request, body, db, SellerProfile)

            # ---- Store ----
            if action == "get_store":
                return await _store.get_store(request, db, Store)
            if action == "create_store":
                return await _store.create_store(request, body, db, Store)
            if action == "update_store":
                return await _store.update_store(request, body, db, Store)

            # ---- X Account ----
            if action == "x_oauth_init":
                return await _x_account.x_oauth_init(request)
            if action == "x_oauth_callback":
                return await _x_account.x_oauth_callback(request, body, db, XAccount, OAuthToken, Product, ProductSyncLog)
            if action == "x_account_status":
                return await _x_account.x_account_status(request, db, XAccount)
            if action == "x_account_disconnect":
                return await _x_account.x_account_disconnect(request, db, XAccount, OAuthToken)
            if action == "x_account_sync":
                return await _x_account.x_account_sync(request, db, XAccount, OAuthToken)
            if action == "x_token_refresh":
                return await _x_account.x_token_refresh(request, db, XAccount, OAuthToken)

            # ---- Products ----
            if action == "sync_products":
                return await _products.sync_products(request, db, Product, ProductSyncLog)
            if action == "get_products":
                return await _products.get_products(request, db, Product, ProductSyncLog)
            if action == "get_product":
                return await _products.get_product(request, body, db, Product, ProductSyncLog)
            if action == "get_sync_logs":
                return await _products.get_sync_logs(request, db, ProductSyncLog)

            # ---- Publish ----
            if action == "publish_product":
                return await _publish.publish_product(request, body, db, Product, PublishJob, XAccount, OAuthToken, PublishedPost)
            if action == "publish_bulk":
                return await _publish.publish_bulk(request, body, db, Product, PublishJob, XAccount, OAuthToken, PublishedPost)
            if action == "schedule_product":
                return await _publish.schedule_product(request, body, db, Product, PublishJob)
            if action == "retry_failed_jobs":
                return await _publish.retry_failed_jobs(request, db, Product, PublishJob, XAccount, OAuthToken, PublishedPost)
            if action == "get_publish_jobs":
                return await _publish.get_publish_jobs(request, db, PublishJob)
            if action == "get_published_posts":
                return await _publish.get_published_posts(request, db, PublishedPost)

            # ---- Dashboard & Analytics ----
            if action == "get_dashboard":
                return await _dashboard.get_dashboard(request, db, Seller, XAccount, Product, PublishJob, Order)
            if action == "get_orders":
                return await _dashboard.get_orders(request, db, Order)
            if action == "get_analytics":
                return await _dashboard.get_analytics(request, db, Product, PublishJob, Order, AnalyticsEvent)

            raise HTTPException(status_code=404, detail=f"action '{action}' not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"error: {e.args}")

    async def i_init(request: Request):
        return

    async def get_schema_for_create(request: Request, params: dict, db: any):
        try:
            body       = await request.json() if await request.body() else {}
            utility_id = None
            if "id" in params:
                result   = await db.execute(select(Instance).where(Instance.id == params['id']))
                instance = result.scalar_one_or_none()
                if not instance:
                    raise Exception("invalid id")
                utility_id = f"{instance.utility_id}"
            if "utility_id" in body:   utility_id = body['utility_id']
            if "utility_id" in params: utility_id = params['utility_id']
            if not utility_id:
                raise Exception("utility_id is not valid")
            lib_name, _lib_ = include_file(f"src/shared/utility/l/{utility_id}/index.py", lambda name, module: ())[0]
            _, get_schema_fn, *_ = await _lib_.index({'data': {}})
            _r      = await get_schema_fn(request)
            _r_body = _r['body']
            _r['body'] = {
                "type": "object",
                "required": ['name', 'project_id', 'utility_id', 'config_id', 'data'],
                "properties": {
                    "name":       {"type": "string", "minLength": 1},
                    "project_id": {"type": "string", "minLength": 1},
                    "utility_id": {"type": "string", "minLength": 1},
                    "config_id":  {"type": ["string", "null"], "minLength": 1},
                    "data":        _r_body['properties']['data'],
                },
                "example": {
                    "id":         "xxxxx-3ab9-4f72-9f34-aeda3ccdd216",
                    "name":       "MY_INSTANCE_NAME",
                    "project_id": "xxxxx-16b6-486c-a7ae-2094ded7caa8",
                    "utility_id": f"{utility_id}",
                    "config_id":  None,
                    "data":        _r_body['example']['data']
                }
            }
            return _r
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Schema validation error: {e.args}")

    async def get_schema_for_run(request: Request, params: dict, db: any):
        try:
            project_name  = params['project']
            instance_name = params['instance']
            result = await db.execute(
                select(Instance)
                .join(Project, Instance.project_id == Project.id)
                .where(Instance.name == instance_name, Project.name == project_name)
                .options(joinedload(Instance.project), joinedload(Instance.utility))
            )
            instance = result.scalar_one_or_none()
            if not instance:
                raise Exception("invalid id")
            utility_id = f"{instance.utility_id}"
            lib_name, _lib_ = include_file(f"src/shared/utility/l/{utility_id}/index.py", lambda name, module: ())[0]
            _, __, get_schema_run_fn, *_ = await _lib_.index({'data': {}})
            return await get_schema_run_fn(request)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Schema validation error: {e.args}")

    async def get_doc_for_run(request: Request, params: dict, db: any):
        try:
            project_name  = params['project']
            instance_name = params['instance']
            result = await db.execute(
                select(Instance)
                .join(Project, Instance.project_id == Project.id)
                .where(Instance.name == instance_name, Project.name == project_name)
                .options(joinedload(Instance.project), joinedload(Instance.utility))
            )
            instance = result.scalar_one_or_none()
            if not instance:
                raise Exception("invalid id")
            utility_id = f"{instance.utility_id}"
            lib_name, _lib_ = include_file(f"src/shared/utility/l/{utility_id}/index.py", lambda name, module: ())[0]
            _, __, ___, __, get_doc_fn = await _lib_.index({'data': {'instance': instance}})
            return await get_doc_fn(request)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Schema validation error: {e.args}")

    return i, get_schema_for_create, get_schema_for_run, i_init, get_doc_for_run
