import os
import secrets
import json
import httpx
import jwt  # Install using: pip install PyJWT
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timedelta
from starlette.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv, find_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from bson import ObjectId  # Import to handle MongoDB ObjectId

load_dotenv(find_dotenv(), verbose=True)

router = APIRouter()

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")  
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")  
GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google/callback"
FRONTEND_REDIRECT_URI = "http://localhost:3000/dashboard"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

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

# MongoDB connection
MONGO_DETAILS = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "student_profile")

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
        print("❌ MongoDB connection closed.")

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

@router.get("/auth/google")
async def google_login():
    state = secrets.token_urlsafe(16)  # CSRF Protection
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
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    async with httpx.AsyncClient() as client:
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = await client.post(GOOGLE_TOKEN_URL, data=token_data, headers=headers)

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        token_json = token_response.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Invalid access token response")

        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(GOOGLE_USER_INFO_URL, headers=headers)
        user_data = user_response.json()

        google_id = user_data.get("sub")
        name = user_data.get("name", "Unknown User")
        email = user_data.get("email")
        picture = user_data.get("picture", "")

        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google response")

        existing_user = await profile_collection.find_one({"email": email})

        if existing_user:
            user_data = serialize_mongo_document(existing_user)
            token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
            
            jwt_payload = {
                "sub": user_data["google_id"],
                "name": user_data["name"],
                "email": user_data["email"],
                "exp": token_expiry  # Ensure expiration time is included
            }
            jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)
            return JSONResponse(content={"token": jwt_token, "user": user_data})

        new_user = {
            "google_id": google_id,  # Ensure google_id is stored
            "name": name,
            "email": email,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await profile_collection.insert_one(new_user)
        new_user["_id"] = str(result.inserted_id)  # Convert `_id` to string immediately

        new_user_serialized = serialize_mongo_document(new_user)
        token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

        jwt_payload = {
            "sub": google_id,
            "name": name,
            "email": email,
            "exp": token_expiry
        }
        jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

        redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={name}&picture={picture}"
        return RedirectResponse(redirect_url)
        # return JSONResponse(content={"token": jwt_token, "user": new_user_serialized})
