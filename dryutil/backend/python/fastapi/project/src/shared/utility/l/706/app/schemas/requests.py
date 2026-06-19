from pydantic import BaseModel
from typing import Optional


class CreateStoreRequest(BaseModel):
    name:           str
    description:    str | None = None
    logo_url:       str | None = None
    banner_url:     str | None = None
    contact_email:  str | None = None
    support_number: str | None = None
    website_url:    str | None = None


class UpdateStoreRequest(BaseModel):
    name:           str | None = None
    description:    str | None = None
    logo_url:       str | None = None
    banner_url:     str | None = None
    contact_email:  str | None = None
    support_number: str | None = None
    website_url:    str | None = None


class GetProductRequest(BaseModel):
    product_id: str


class PublishProductRequest(BaseModel):
    product_id: str
    text:       str | None = None


class PublishBulkRequest(BaseModel):
    product_ids: list[str]


class ScheduleProductRequest(BaseModel):
    product_id:   str
    scheduled_at: str   # ISO 8601 datetime string


class OAuthCallbackRequest(BaseModel):
    code:  str
    state: str
