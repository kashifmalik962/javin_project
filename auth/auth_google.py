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
from pymongo import DESCENDING

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
TOKEN_EXPIRE_MINUTES = int(os.getenv("USER_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# MongoDB Global Variables
client = None
database: AsyncIOMotorDatabase = None
fs = None
profile_collection = None

# MongoDB connection
MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb+srv://kashifmalik2786:BhWKQzVyaxRfzNti@cluster0.ctpzucp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "WTT_DB")

async def connect_to_mongo():
    global client, database, fs, profile_collection
    client = AsyncIOMotorClient(MONGO_DETAILS, maxPoolSize=100)
    database = client[DATABASE_NAME]
    fs = AsyncIOMotorGridFSBucket(database)
    profile_collection = database["user_profiles"]
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

@router.get("/auth/google/callback", include_in_schema=False)
async def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=200, detail="Authorization code not found")

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
            raise HTTPException(status_code=200, detail="Failed to get access token")
        
        token_json = token_response.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(status_code=200, detail="Invalid access token response")

        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(GOOGLE_USER_INFO_URL, headers=headers)
        user_data = user_response.json()

        print("🔹 Google User Data:", user_data)

        full_name = user_data.get("name", "Unknown User")
        email = user_data.get("email")
        picture = user_data.get("picture")

        if not email:
            raise HTTPException(status_code=200, detail="Email not found in Google response")

        # existing_user = await profile_collection.find_one({"email": email})
        existing_user = await profile_collection.find_one({
            "$or": [{"email": email}, {"email2": email}]
        })

        if existing_user:
            print(existing_user, "existing_user")
            user_active = existing_user.get("active")
            if user_active != "true":
                raise HTTPException(status_code=200, detail="user Inactivated from Admin side.")
            
            user_data = serialize_mongo_document(existing_user)
            token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
            
            jwt_payload = {
                "full_name": user_data["full_name"],
                "email": user_data["email"],
                "exp": token_expiry  # Ensure expiration time is included
            }
            jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)
            print(full_name, "full_name ===----===")
            redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={full_name}&picture={picture}"
            return RedirectResponse(redirect_url)
            # return JSONResponse(status_code=200,content={"token": jwt_token, "user": user_data})

        
        last_user = await profile_collection.find_one({}, sort=[("user_id", DESCENDING)])
        user_id = 101 if last_user is None else last_user["user_id"] + 1

        # 🔹 If user does not exist, insert new user
        new_user = {
            "full_name": full_name,
            "email": email,
            "user_id": user_id,
            "active": "true",
            "profile_type": "primary",
            "picture": picture
        }

        # ✅ Fill missing fields with None
        default_fields = [
            "email2", "phone", "phone2", "country", "address",
            "resume_name", "linkedin", "current_city", "preferred_city",
            "summary_of_profile", "college_background", "current_organization",
            "total_work_experience_years", "comment", "referred_by",
            "current_ctc", "desired_ctc", "github", "leetcode",
            "codechef", "sub_user_id", "picture"
        ]

        for field in default_fields:
            new_user.setdefault(field, None)  # Use setdefault to avoid overwriting existing values

        print("✅ Creating new user")

        result = await profile_collection.insert_one(new_user)
        new_user["_id"] = str(result.inserted_id)  # Convert `_id` to string immediately

        created_profile = await profile_collection.find_one({"_id": ObjectId(new_user["_id"])}, {"_id": 0})

        # Profile Completeness in percentage
        rest_feilds = ["email", "phone", "sub_user_id", "referred_by", "profile_type", "active", "user_id"]
        number_of_fields = len(created_profile) - len(rest_feilds)
        # print(created_profile, "created_profile")
        # null_fields = [key for key, value in created_profile.items() if value is None]
        null_fields = []
        for key, value in created_profile.items():
            if value is None and key not in rest_feilds:
                print(key, value, "key, value")
                null_fields.append(key)

        completeness_precent = 100 - ((len(null_fields)/number_of_fields)*100)
        update_profile_complete = await profile_collection.update_one(
            {"_id": ObjectId(new_user["_id"])}, 
            {"$set": {"profile_complete": completeness_precent}}
        )

        new_user_serialized = serialize_mongo_document(new_user)
        token_expiry = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

        jwt_payload = {
            "name": full_name,
            "email": email,
            "exp": token_expiry
        }
        print(new_user_serialized, "new_user_serialized")
        
        jwt_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)
        print(jwt_token, "jwt_token ++")

        redirect_url = f"{FRONTEND_REDIRECT_URI}?token={jwt_token}&email={email}&name={full_name}&picture={picture}"
        return RedirectResponse(redirect_url)
        # return JSONResponse(status_code=200, content={"token": jwt_token, "user": new_user_serialized})
