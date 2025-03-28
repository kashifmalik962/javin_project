import os
import secrets
import json
import httpx
import asyncio
import jwt
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from datetime import datetime, timedelta
from bson import ObjectId  # Import to handle MongoDB ObjectId
from starlette.responses import JSONResponse
from pymongo import DESCENDING


router = APIRouter()

# MongoDB connection details
MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb+srv://kashifmalik962:gYxgUGO6622a1cRr@cluster0.aad1d.mongodb.net/node_mongo_crud?")
DATABASE_NAME = os.getenv("DATABASE_NAME", "student_profile")

# LinkedIn OAuth Config
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")  
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")  
LINKEDIN_REDIRECT_URI = "http://localhost:8000/auth/linkedin/callback"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"
FRONTEND_REDIRECT_URI = "http://localhost:3000/dashboard"

# OAuth Scopes
SCOPES = ["openid", "profile", "email"]

# JWT Secret Key
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# MongoDB Global Variables
client = None
database: AsyncIOMotorDatabase = None
fs = None
profile_collection = None

# ✅ Initialize MongoDB in FastAPI's event loop
async def connect_to_mongo():
    global client, database, fs, profile_collection
    client = AsyncIOMotorClient(MONGO_DETAILS, maxPoolSize=100)
    database = client[DATABASE_NAME]
    fs = AsyncIOMotorGridFSBucket(database)
    profile_collection = database["profiles"]
    print("✅ Connected to MongoDB successfully!")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")

# ✅ FastAPI Startup & Shutdown Events
@router.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@router.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()


def serialize_mongo_document(doc):
    """Convert MongoDB document to JSON serializable format."""
    if isinstance(doc, dict):
        return {k: serialize_mongo_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_mongo_document(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)  # Convert ObjectId to string
    elif isinstance(doc, datetime):
        return doc.isoformat()  # Convert datetime to ISO format
    return doc

# ✅ LinkedIn Login Route
@router.get("/auth/linkedin")
async def linkedin_login():
    """Redirect user to LinkedIn login page"""
    state = secrets.token_urlsafe(16)  # CSRF state token
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state
    }
    auth_url = f"{LINKEDIN_AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return RedirectResponse(auth_url)

# ✅ LinkedIn Callback Route
@router.get("/auth/linkedin/callback")
async def linkedin_callback(request: Request):
    """Handle LinkedIn OAuth Callback"""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=200, detail="Authorization code not found")

    async with httpx.AsyncClient() as client:
        # 🔹 Exchange Code for Token
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
            raise HTTPException(status_code=200, detail="Invalid response from LinkedIn")

        if "access_token" not in token_json:
            raise HTTPException(status_code=200, detail=f"Failed to get access token: {token_json}")

        access_token = token_json["access_token"]

        # 🔹 Fetch User Info
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(LINKEDIN_USER_INFO_URL, headers=headers)
        user_data = user_response.json()

        print("🔹 LinkedIn User Data:", user_data)

        # 🔹 Extract user details
        full_name = user_data.get("name", "Unknown User")  # Ensure default values
        email = user_data.get("email")

        if not email:
            raise HTTPException(status_code=200, detail="Email not found in LinkedIn response")

        # 🔹 Check if user exists in DB
        existing_user = await profile_collection.find_one({"email": email})

        if existing_user:
            print("Existing user found")
            user_data = serialize_mongo_document(existing_user)
            token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

            jwt_payload = {
                "full_name": existing_user["full_name"],
                "email": existing_user["email"],
                "exp": token_expiry  # Ensure token expiration
            }
            jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)
            redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={full_name}"
            return RedirectResponse(redirect_url)
            # return JSONResponse(status_code=200,content={"token": jwt_token, "user": user_data})



        last_student = await profile_collection.find_one({}, sort=[("student_id", DESCENDING)])
        student_id = 101 if last_student is None else last_student["student_id"] + 1

        # 🔹 If user does not exist, insert new user
        new_user = {
            "full_name": full_name,
            "email": email,
            "student_id": student_id,
            "profile_type": "primary"
        }

        # ✅ Fill missing fields with None
        default_fields = [
            "email2", "phone", "phone2", "country", "address",
            "resume_name", "linkedin", "current_city", "preferred_city",
            "summary_of_profile", "college_background", "current_organization",
            "total_work_experience_years", "comment", "referred_by",
            "current_ctc", "desired_ctc", "github", "leetcode",
            "codechef", "sub_student_id"
        ]

        for field in default_fields:
            new_user.setdefault(field, None)  # Use setdefault to avoid overwriting existing values

        print("✅ Creating new user")

        result = await profile_collection.insert_one(new_user)
        new_user["_id"] = str(result.inserted_id)  # Convert `_id` to string immediately

        new_user_serialized = serialize_mongo_document(new_user)
        token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

        print(new_user_serialized, "new_user_serialized")
        # 🔹 Generate JWT Token for new user
        jwt_payload = {
            "name": full_name,
            "email": email,
            "exp": token_expiry  # Ensure token expiration
        }
        jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

        print(jwt_token, "jwt_token ++")
        # 🔹 Redirect to React App with JWT Token
        redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={full_name}"
        return RedirectResponse(redirect_url)
        # return JSONResponse(status_code=200, content={"token": jwt_token, "user": new_user_serialized})

