import os
import httpx
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

app = FastAPI()
router = APIRouter()

# LinkedIn Credentials
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/linkedin/callback"

# Step 1: Redirect User to LinkedIn Auth Page
@app.get("/auth/linkedin")
async def linkedin_login():
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&scope=r_liteprofile%20r_emailaddress"
    )
    return JSONResponse({"auth_url": auth_url})

# Step 2: LinkedIn Callback (Exchange Code for Access Token)
@app.get("/auth/linkedin/callback")
async def linkedin_callback(code: str):
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, headers=headers, data=data)
        token_data = token_response.json()

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail="Failed to get access token")

    access_token = token_data["access_token"]

    # Step 3: Fetch User Profile from LinkedIn
    user_info = await fetch_linkedin_user(access_token)

    return JSONResponse({"message": "User authenticated", "user_info": user_info})

# Fetch User Data from LinkedIn API
async def fetch_linkedin_user(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        profile_response = await client.get("https://api.linkedin.com/v2/me", headers=headers)
        email_response = await client.get("https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))", headers=headers)

    if profile_response.status_code != 200 or email_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user data")

    profile_data = profile_response.json()
    email_data = email_response.json()

    return {
        "id": profile_data.get("id"),
        "first_name": profile_data.get("localizedFirstName"),
        "last_name": profile_data.get("localizedLastName"),
        "profile_picture": profile_data.get("profilePicture", {}).get("displayImage", ""),
        "headline": profile_data.get("headline", ""),
        "email": email_data.get("elements", [{}])[0].get("handle~", {}).get("emailAddress", ""),
    }
