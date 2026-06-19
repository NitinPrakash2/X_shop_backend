import os
import httpx
from datetime import datetime, timezone, timedelta

X_CLIENT_ID     = os.getenv("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET", "")
X_TOKEN_URL     = "https://api.twitter.com/2/oauth2/token"
X_TWEET_URL     = "https://api.twitter.com/2/tweets"
X_USER_URL      = "https://api.twitter.com/2/users/me?user.fields=id,name,username,description,profile_image_url,public_metrics"


async def fetch_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(X_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code != 200:
            raise RuntimeError(f"X user fetch failed: {resp.text}")
        return resp.json().get("data", {})


async def post_tweet(access_token: str, text: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            X_TWEET_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"text": text}
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"tweet failed: {resp.text}")
        return resp.json()["data"]["id"]


async def exchange_code_for_token(code: str, redirect_uri: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(X_TOKEN_URL, data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "code_verifier": code_verifier,
        }, auth=(X_CLIENT_ID, X_CLIENT_SECRET))
        if resp.status_code != 200:
            raise RuntimeError(f"token exchange failed: {resp.text}")
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(X_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        }, auth=(X_CLIENT_ID, X_CLIENT_SECRET))
        if resp.status_code != 200:
            raise RuntimeError(f"token refresh failed: {resp.text}")
        return resp.json()


async def get_valid_token(token_row, db) -> str:
    """Returns valid access token, auto-refreshes if expiring within 5 min."""
    if token_row.token_expiry:
        if token_row.token_expiry - datetime.now(timezone.utc) < timedelta(minutes=5):
            if token_row.refresh_token:
                data = await refresh_access_token(token_row.refresh_token)
                token_row.access_token  = data["access_token"]
                token_row.refresh_token = data.get("refresh_token", token_row.refresh_token)
                if "expires_in" in data:
                    token_row.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
                await db.commit()
    return token_row.access_token
