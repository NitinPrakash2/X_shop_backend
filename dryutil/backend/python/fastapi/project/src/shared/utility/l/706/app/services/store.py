import importlib.util
import os as _os
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


def _load_schemas():
    path = _os.path.join(_os.path.dirname(__file__), "..", "schemas", "requests.py")
    spec = importlib.util.spec_from_file_location("xshop_schema_req", _os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def get_store(request: Request, db: AsyncSession, Store) -> JSONResponse:
    seller_id = request.state.user["id"]
    store     = (await db.execute(select(Store).where(Store.seller_id == seller_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(404, "store not found")
    return JSONResponse({"status": "success", "output": {
        "id":             str(store.id),
        "name":           store.name,
        "description":    store.description,
        "logo_url":       store.logo_url,
        "banner_url":     store.banner_url,
        "contact_email":  store.contact_email,
        "support_number": store.support_number,
        "website_url":    store.website_url,
    }})


async def create_store(request: Request, body: dict, db: AsyncSession, Store) -> JSONResponse:
    seller_id = request.state.user["id"]
    schemas   = _load_schemas()
    try:
        req = schemas.CreateStoreRequest(**body)
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e))

    existing = (await db.execute(select(Store).where(Store.seller_id == seller_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "store already exists, use update_store")

    store = Store(
        seller_id      = seller_id,
        name           = req.name,
        description    = req.description,
        logo_url       = req.logo_url,
        banner_url     = req.banner_url,
        contact_email  = req.contact_email,
        support_number = req.support_number,
        website_url    = req.website_url,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return JSONResponse({"status": "success", "output": {"id": str(store.id), "name": store.name}}, status_code=201)


async def update_store(request: Request, body: dict, db: AsyncSession, Store) -> JSONResponse:
    seller_id = request.state.user["id"]
    schemas   = _load_schemas()
    try:
        req = schemas.UpdateStoreRequest(**body)
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e))

    store = (await db.execute(select(Store).where(Store.seller_id == seller_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(404, "store not found")

    for field in ["name", "description", "logo_url", "banner_url", "contact_email", "support_number", "website_url"]:
        val = getattr(req, field)
        if val is not None:
            setattr(store, field, val)
    await db.commit()
    return JSONResponse({"status": "success", "output": {"id": str(store.id), "name": store.name}})
