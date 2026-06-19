import os
import base64
import hashlib
import secrets
import urllib.parse
import importlib.util
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

X_CLIENT_ID    = os.getenv("X_CLIENT_ID", "")
X_CALLBACK_URL = os.getenv("X_CALLBACK_URL", "http://localhost:8000/client-public/api/i/ona/xshop?action=x_oauth_callback")
X_SCOPES       = "tweet.read tweet.write users.read offline.access"
X_AUTH_URL     = "https://twitter.com/i/oauth2/authorize"

_pkce_store: dict = {}


def _load_x_client():
    path = os.path.join(os.path.dirname(__file__), "..", "integrations", "x", "client.py")
    spec = importlib.util.spec_from_file_location("xshop_x_client", os.path.abspath(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_pkce() -> tuple[str, str]:
    code_verifier  = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _build_oauth_url(state: str, code_challenge: str) -> str:
    params = {
        "response_type":         "code",
        "client_id":             X_CLIENT_ID,
        "redirect_uri":          X_CALLBACK_URL,
        "scope":                 X_SCOPES,
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": "S256",
    }
    return X_AUTH_URL + "?" + urllib.parse.urlencode(params)


async def x_oauth_init(request: Request) -> JSONResponse:
    seller_id               = request.state.user["id"]
    code_verifier, code_challenge = _make_pkce()
    state                   = str(seller_id)
    _pkce_store[state]      = code_verifier
    return JSONResponse({"status": "success", "output": {
        "oauth_url": _build_oauth_url(state, code_challenge)
    }})


async def x_oauth_callback(request: Request, body: dict, db: AsyncSession, XAccount, OAuthToken, Product=None, ProductSyncLog=None) -> JSONResponse:
    code      = body.get("code") or request.query_params.get("code")
    state     = body.get("state") or request.query_params.get("state")
    seller_id = state
    if not code or not state:
        raise HTTPException(422, "code and state required")

    code_verifier = _pkce_store.pop(state, None)
    if code_verifier is None:
        raise HTTPException(400, "invalid or expired oauth state")

    x = _load_x_client()

    # 1. Exchange code for token
    token_data = await x.exchange_code_for_token(code, X_CALLBACK_URL, code_verifier)

    # 2. Fetch X user info
    user_data = await x.fetch_user_info(token_data["access_token"])
    metrics   = user_data.get("public_metrics", {})

    # 3. Upsert XAccount
    x_acc = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc:
        x_acc = XAccount(seller_id=seller_id)
        db.add(x_acc)
        await db.flush()

    x_acc.x_user_id         = user_data.get("id")
    x_acc.username          = user_data.get("username")
    x_acc.display_name      = user_data.get("name")
    x_acc.profile_image_url = user_data.get("profile_image_url")
    x_acc.bio               = user_data.get("description")
    x_acc.followers_count   = metrics.get("followers_count", 0)
    x_acc.following_count   = metrics.get("following_count", 0)
    x_acc.is_connected      = True
    x_acc.last_synced_at    = datetime.now(timezone.utc)
    x_acc.account_meta      = user_data

    # 4. Upsert OAuthToken
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if not token_row:
        token_row = OAuthToken(x_account_id=x_acc.id)
        db.add(token_row)

    token_row.access_token  = token_data["access_token"]
    token_row.refresh_token = token_data.get("refresh_token")
    token_row.scope         = token_data.get("scope")
    if "expires_in" in token_data:
        token_row.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    await db.commit()

    # 5. Auto-trigger product sync in background (non-blocking)
    if Product and ProductSyncLog:
        try:
            import asyncio
            sync_path = os.path.join(os.path.dirname(__file__), "..", "tasks", "sync_products.py")
            spec      = importlib.util.spec_from_file_location("xshop_task_sync", os.path.abspath(sync_path))
            sync_mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sync_mod)
            asyncio.create_task(sync_mod.run_product_sync(seller_id, db, Product, ProductSyncLog))
        except (ValueError, TypeError, KeyError, IOError):
            pass  # sync failure must not break OAuth flow

    return JSONResponse({"status": "success", "output": {
        "username":     x_acc.username,
        "display_name": x_acc.display_name,
        "is_connected": x_acc.is_connected,
        "auto_sync":    "product sync triggered in background",
    }})


async def x_account_status(request: Request, db: AsyncSession, XAccount) -> JSONResponse:
    seller_id = request.state.user["id"]
    x_acc     = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc:
        return JSONResponse({"status": "success", "output": {"is_connected": False}})
    return JSONResponse({"status": "success", "output": {
        "is_connected":      x_acc.is_connected,
        "x_user_id":         x_acc.x_user_id,
        "username":          x_acc.username,
        "display_name":      x_acc.display_name,
        "profile_image_url": x_acc.profile_image_url,
        "bio":               x_acc.bio,
        "followers_count":   x_acc.followers_count,
        "following_count":   x_acc.following_count,
        "last_synced_at":    x_acc.last_synced_at.isoformat() if x_acc.last_synced_at else None,
    }})


async def x_account_disconnect(request: Request, db: AsyncSession, XAccount, OAuthToken) -> JSONResponse:
    seller_id = request.state.user["id"]
    x_acc     = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc:
        raise HTTPException(404, "x account not found")
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if token_row:
        await db.delete(token_row)
    x_acc.is_connected = False
    x_acc.x_user_id    = None
    x_acc.account_meta = None
    await db.commit()
    return JSONResponse({"status": "success", "output": {"is_connected": False}})


async def x_account_sync(request: Request, db: AsyncSession, XAccount, OAuthToken) -> JSONResponse:
    seller_id = request.state.user["id"]
    x_acc     = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc or not x_acc.is_connected:
        raise HTTPException(400, "x account not connected")
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if not token_row:
        raise HTTPException(400, "no oauth token found")

    x            = _load_x_client()
    access_token = await x.get_valid_token(token_row, db)
    user_data    = await x.fetch_user_info(access_token)
    metrics      = user_data.get("public_metrics", {})

    x_acc.username          = user_data.get("username")
    x_acc.display_name      = user_data.get("name")
    x_acc.profile_image_url = user_data.get("profile_image_url")
    x_acc.bio               = user_data.get("description")
    x_acc.followers_count   = metrics.get("followers_count", 0)
    x_acc.following_count   = metrics.get("following_count", 0)
    x_acc.last_synced_at    = datetime.now(timezone.utc)
    x_acc.account_meta      = user_data
    await db.commit()
    return JSONResponse({"status": "success", "output": {"synced": True, "username": x_acc.username}})


async def x_token_refresh(request: Request, db: AsyncSession, XAccount, OAuthToken) -> JSONResponse:
    seller_id = request.state.user["id"]
    x_acc     = (await db.execute(select(XAccount).where(XAccount.seller_id == seller_id))).scalar_one_or_none()
    if not x_acc:
        raise HTTPException(404, "x account not found")
    token_row = (await db.execute(select(OAuthToken).where(OAuthToken.x_account_id == x_acc.id))).scalar_one_or_none()
    if not token_row or not token_row.refresh_token:
        raise HTTPException(400, "no refresh token found")
    x    = _load_x_client()
    data = await x.refresh_access_token(token_row.refresh_token)
    token_row.access_token  = data["access_token"]
    token_row.refresh_token = data.get("refresh_token", token_row.refresh_token)
    if "expires_in" in data:
        token_row.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    await db.commit()
    return JSONResponse({"status": "success", "output": {"refreshed": True}})
