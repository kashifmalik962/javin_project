import os
import secrets
import json
import httpx
import jwt  # Install using: pip install PyJWT
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timedelta
from starlette.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), verbose=True)


router = APIRouter()

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")  
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")  
GOOGLE_REDIRECT_URI = "https://javin-project.onrender.com/auth/google/callback"
FRONTEND_REDIRECT_URI = "http://localhost:3000/dashboard"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Secret key for JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

SCOPES = ["openid", "email", "profile"]

@router.get("/auth/google")
async def google_login():
    """Redirect user to Google login page"""
    state = secrets.token_urlsafe(16)  # ✅ CSRF Protection
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return RedirectResponse(auth_url)

@router.get("/auth/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth Callback"""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    async with httpx.AsyncClient() as client:
        # Exchange Code for Access Token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = await client.post(GOOGLE_TOKEN_URL, data=token_data, headers=headers)

        try:
            token_json = token_response.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid response from Google")

        if "access_token" not in token_json:
            raise HTTPException(status_code=400, detail=f"Failed to get access token: {token_json}")

        access_token = token_json["access_token"]

        # Fetch User Info
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(GOOGLE_USER_INFO_URL, headers=headers)
        user_data = user_response.json()

        print("🔹 Google User Data:", user_data)

        # ✅ Generate JWT Token
        token_expiry = datetime.utcnow() + timedelta(minutes=int(TOKEN_EXPIRE_MINUTES))
        jwt_payload = {
            "sub": user_data["sub"],
            "name": user_data["name"],
            "email": user_data["email"],
            "picture": user_data["picture"],
            "exp": token_expiry
        }
        jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

        # ✅ Redirect to React App with user data
        # redirect_url = f"{FRONTEND_REDIRECT_URI}?name={user_data['name']}&email={user_data['email']}&picture={user_data['picture']}&token={jwt_token}"
        # return RedirectResponse(redirect_url)
        return JSONResponse(content={"token": jwt_token, "user": user_data})
    