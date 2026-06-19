import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.util.jwt_handler.index import JWTHandler


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def _verify(password: str, hashed: str) -> bool:
    return _hash(password) == hashed

def _issue_tokens(seller_id: str, email: str) -> tuple[str, str]:
    access_token  = JWTHandler.create_token({
        "sub": seller_id, "email": email,
        "security": {"party": ["party_2"]},
        "type": "access"
    })
    refresh_token = secrets.token_urlsafe(48)
    return access_token, refresh_token


async def register(body: dict, db: AsyncSession, Seller, SellerProfile, SellerRefreshToken) -> JSONResponse:
    import importlib, os, sys
    _base = os.path.join(os.path.dirname(__file__), "..", "schemas", "auth.py")
    spec  = __import__("importlib").util.spec_from_file_location("xshop_schema_auth", os.path.abspath(_base))
    mod   = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        req = mod.RegisterRequest(**body)
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e))

    from sqlalchemy.future import select
    existing = (await db.execute(select(Seller).where(Seller.email == req.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "email already registered")

    seller = Seller(email=req.email, password_hash=_hash(req.password))
    db.add(seller)
    await db.flush()
    db.add(SellerProfile(seller_id=seller.id, full_name=req.full_name))
    await db.flush()

    access_token, refresh_token = _issue_tokens(str(seller.id), seller.email)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.add(SellerRefreshToken(
        seller_id=seller.id,
        token_hash=_hash(refresh_token),
        expires_at=expires_at
    ))
    await db.commit()
    await db.refresh(seller)
    return JSONResponse({
        "status": "success",
        "output": {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "seller": {"id": str(seller.id), "email": seller.email}
        }
    }, status_code=201)


async def login(body: dict, db: AsyncSession, Seller, SellerRefreshToken) -> JSONResponse:
    import os
    _base = os.path.join(os.path.dirname(__file__), "..", "schemas", "auth.py")
    spec  = __import__("importlib").util.spec_from_file_location("xshop_schema_auth", os.path.abspath(_base))
    mod   = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        req = mod.LoginRequest(**body)
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e))

    from sqlalchemy.future import select
    seller = (await db.execute(select(Seller).where(Seller.email == req.email))).scalar_one_or_none()
    if not seller or not _verify(req.password, seller.password_hash):
        raise HTTPException(401, "invalid credentials")
    if not seller.is_active:
        raise HTTPException(403, "account deactivated")

    access_token, refresh_token = _issue_tokens(str(seller.id), seller.email)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    existing_rt = (await db.execute(
        select(SellerRefreshToken).where(SellerRefreshToken.seller_id == seller.id)
    )).scalar_one_or_none()
    if existing_rt:
        existing_rt.token_hash = _hash(refresh_token)
        existing_rt.expires_at = expires_at
        existing_rt.is_revoked = False
    else:
        db.add(SellerRefreshToken(
            seller_id=seller.id, token_hash=_hash(refresh_token), expires_at=expires_at
        ))
    await db.commit()
    return JSONResponse({
        "status": "success",
        "output": {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "seller": {"id": str(seller.id), "email": seller.email}
        }
    })


async def refresh_token(body: dict, db: AsyncSession, Seller, SellerRefreshToken) -> JSONResponse:
    token = (body.get("refresh_token") or "").strip()
    if token == "":
        raise HTTPException(422, "refresh_token required")

    from sqlalchemy.future import select
    token_hash = _hash(token)
    row = (await db.execute(
        select(SellerRefreshToken).where(
            SellerRefreshToken.token_hash == token_hash,
            SellerRefreshToken.is_revoked is False
        )
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(401, "invalid or revoked refresh token")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "refresh token expired")

    seller = (await db.execute(select(Seller).where(Seller.id == row.seller_id))).scalar_one_or_none()
    if not seller or not seller.is_active:
        raise HTTPException(401, "seller not found or deactivated")

    new_access, new_refresh = _issue_tokens(str(seller.id), seller.email)
    row.token_hash = _hash(new_refresh)
    row.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.commit()
    return JSONResponse({
        "status": "success",
        "output": {
            "access_token":  new_access,
            "refresh_token": new_refresh,
        }
    })


async def logout(request: Request, db: AsyncSession, SellerRefreshToken) -> JSONResponse:
    seller_id = request.state.user["id"]
    from sqlalchemy.future import select
    row = (await db.execute(
        select(SellerRefreshToken).where(SellerRefreshToken.seller_id == seller_id)
    )).scalar_one_or_none()
    if row:
        row.is_revoked = True
        await db.commit()
    return JSONResponse({"status": "success", "output": {"logged_out": True}})


async def me(request: Request, db: AsyncSession, Seller, SellerProfile) -> JSONResponse:
    seller_id = request.state.user["id"]
    from sqlalchemy.future import select
    seller  = (await db.execute(select(Seller).where(Seller.id == seller_id))).scalar_one_or_none()
    if not seller:
        raise HTTPException(404, "seller not found")
    profile = (await db.execute(select(SellerProfile).where(SellerProfile.seller_id == seller.id))).scalar_one_or_none()
    return JSONResponse({"status": "success", "output": {
        "id":        str(seller.id),
        "email":     seller.email,
        "is_active": seller.is_active,
        "full_name": profile.full_name if profile else None,
        "phone":     profile.phone     if profile else None,
    }})


async def update_profile(request: Request, body: dict, db: AsyncSession, SellerProfile) -> JSONResponse:
    seller_id = request.state.user["id"]
    from sqlalchemy.future import select
    profile = (await db.execute(select(SellerProfile).where(SellerProfile.seller_id == seller_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "profile not found")
    if "full_name" in body: profile.full_name = body["full_name"]
    if "phone"     in body: profile.phone     = body["phone"]
    await db.commit()
    return JSONResponse({"status": "success", "output": {
        "full_name": profile.full_name,
        "phone":     profile.phone,
    }})
