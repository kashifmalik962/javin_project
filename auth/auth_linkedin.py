import os
import secrets
import json
import httpx
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse
from datetime import datetime, timedelta
import jwt
from starlette.responses import JSONResponse, RedirectResponse

router = APIRouter()

# LinkedIn OAuth Config
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")  
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")  
LINKEDIN_REDIRECT_URI = "https://javin-project.onrender.com/auth/linkedin/callback"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"
FRONTEND_REDIRECT_URI = "http://localhost:3000/dashboard"  # ✅ Redirect to frontend


# OAuth Scopes
SCOPES = ["openid", "profile", "email"]


# Secret key for JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))


@router.get("/auth/linkedin")
async def linkedin_login():
    """Redirect user to LinkedIn login page"""
    state = secrets.token_urlsafe(16)  # ✅ Generate CSRF state token
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state
    }
    auth_url = f"{LINKEDIN_AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return RedirectResponse(auth_url)

@router.get("/auth/linkedin/callback")
async def linkedin_callback(request: Request):
    """Handle LinkedIn OAuth Callback"""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    async with httpx.AsyncClient() as client:
        # Exchange Code for Token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": LINKEDIN_REDIRECT_URI,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = await client.post(LINKEDIN_TOKEN_URL, data=token_data, headers=headers)

        try:
            token_json = token_response.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid response from LinkedIn")

        if "access_token" not in token_json:
            raise HTTPException(status_code=400, detail=f"Failed to get access token: {token_json}")

        access_token = token_json["access_token"]

        # Fetch User Info
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(LINKEDIN_USER_INFO_URL, headers=headers)
        user_data = user_response.json()

        print("🔹 LinkedIn User Data:", user_data)

        # Extract user details
        name = user_data.get("name")
        email = user_data.get("email")
        picture = user_data.get("picture")

        token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

        print(user_data.get("sub"), name, email, picture, token_expiry, "++++++++++++")
        jwt_payload = {
            "sub": user_data.get("sub"),
            "name": name,
            "email": email,
            "picture": picture,
            "exp": token_expiry
        }
        jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

        # ✅ Redirect to React App with user data
        # redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={name}&picture={picture}"
        # return RedirectResponse(redirect_url)

        return JSONResponse(content={"token": jwt_token, "user": user_data})
