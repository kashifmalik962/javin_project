from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
import os
from fastapi import Form
import gridfs
import json
from fastapi.responses import StreamingResponse
import io
from bson.errors import InvalidId
from utils.util import *
from pydantic_model.req_body import *
import random
from datetime import datetime, timedelta
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from auth.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

app = FastAPI()

# MongoDB connection
MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb+srv://kashifmalik962:gYxgUGO6622a1cRr@cluster0.aad1d.mongodb.net/node_mongo_crud?")
DATABASE_NAME = os.getenv("DATABASE_NAME", "student_profile")
PORT = int(os.getenv("PORT", 8000))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


try:
    client = AsyncIOMotorClient(MONGO_DETAILS, maxPoolSize=100)
    database: AsyncIOMotorDatabase = client[DATABASE_NAME]
    database = client[DATABASE_NAME]
    fs = AsyncIOMotorGridFSBucket(database)
    profile_collection = database["profiles"]
    otp_collection = database["otp_collection"]
    admin_collection = database["admin"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB. Error: {e}")



# Register - User
@app.post("/register_student")
async def register_student(student: RegisterStudent):
    if await profile_collection.find_one({"$or": [{"email": student.email}, {"phone": student.phone}]}):
        raise HTTPException(status_code=409, detail="student already exists.")
    
    print("+++++++++++++")
    
    last_student = await profile_collection.find_one({}, sort=[("student_id", -1)])
    student_id = 101 if last_student is None else last_student["student_id"] + 1

    # Convert Pydantic model to dictionary
    student_data = student.model_dump()
    student_data["student_id"] = student_id

    print(student_data, "student_data +++++++++")
    result = await profile_collection.insert_one(student_data)
    inserted_id = result.inserted_id

    print(inserted_id, "inserted_id +++++++++")
    created_profile = await profile_collection.find_one({"_id": inserted_id}, {"_id": 0})

    print(created_profile, "created_profile +++++++++")
    return JSONResponse(status_code=201, content={
        "message": "Successfully Registered Student.",
        "data": created_profile
    })


# Login - Student 
@app.post("/login_student")
async def login_student(login_student:LoginStudent):
    print(login_student, "login_student")
    profile_details =  await profile_collection.find_one(
        {"email":login_student.email, "phone":login_student.phone},
        {"_id": 0, "email":1, "phone":1})
    
    print(profile_details, "profile_details ----->")
    if not profile_details:
        raise HTTPException(status_code=404, detail="student does not exists.")
    
    print(profile_details, "profile_details")

    token_data = {
        "sub": profile_details["email"],
        "student_id": profile_details.get("student_id"),
        "phone": profile_details["phone"]
    }

    access_token = create_access_token(data=token_data)
    
    return JSONResponse(status_code=200, content={
        "message": "Successfully logged in.",
        "access_token": access_token,
        "token_expire_minute": ACCESS_TOKEN_EXPIRE_MINUTES,
        "token_type": "bearer",
        "data": profile_details
    })


# GET - STUDENT DETAILS
@app.get("/get_student/{student_id}")
async def get_student(student_id: int):
    student_details = await profile_collection.find_one({"student_id":student_id}, {"_id": 0, "resume_name":0})

    if not student_details:
        raise HTTPException(status_code=404, detail="students does not exists.")

    return JSONResponse(status_code=200, content={
        "message": "successfully data recieved.",
        "data": student_details
    })


# Update - User
@app.put("/update_user/{student_id}")
async def update_user(student_id: int, request: Request, profile: Profile):
    try:
        profile: Dict[str, Any] = await request.json()  # JSON body ko dict me convert karein

        if not profile:
            raise HTTPException(status_code=400, detail="Request body cannot be empty.")

        print(profile, "profile")

        # Check if the user exists
        existing_user = await profile_collection.find_one({"student_id": student_id})
        if not existing_user:
            raise HTTPException(status_code=404, detail="User does not exist!")

        # Update only the provided fields
        result = await profile_collection.update_one(
            {"student_id": student_id},
            {"$set": profile}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made to the profile.")

        return JSONResponse(
            status_code=200,
            content={"message": "Profile updated successfully!", "profile": profile}
        )

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error updating profile: {str(e)}"})
    

# PATCH - UPDATE STUDENT REACORD
@app.patch("/update_user/{student_id}")
async def update_user(student_id: int, request: Request):
    try:
        profile_updates: Dict[str, Any] = await request.json()  # Get JSON data

        if not profile_updates:
            raise HTTPException(status_code=400, detail="Request body cannot be empty.")

        print(profile_updates, "profile_updates")

        # Check if the user exists
        existing_user = await profile_collection.find_one({"student_id": student_id})
        if not existing_user:
            raise HTTPException(status_code=404, detail="User does not exist!")

        # Remove fields with `None` values (ignores missing fields)
        profile_updates = {k: v for k, v in profile_updates.items() if v is not None}

        if not profile_updates:  # If no valid fields remain
            raise HTTPException(status_code=400, detail="No valid fields provided for update.")

        # Update only the provided fields
        result = await profile_collection.update_one(
            {"student_id": student_id},
            {"$set": profile_updates}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made to the profile.")

        # Fetch updated user data
        updated_user = await profile_collection.find_one({"student_id": student_id}, {"_id": 0})

        return JSONResponse(
            status_code=200,
            content={"message": "Profile updated successfully!", "profile": updated_user}
        )

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error updating profile: {str(e)}"})
    
    

# Send OTP to the user
@app.post("/student/send_otp_watsappp")
async def send_otp_watsapp(phone: Send_Otp_Number):
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    # Generate 6-digit OTP
    otp_code = random.randint(100000, 999999)

    otp_data = {
        "phone": phone.phone,
        "otp": encode_base64(str(otp_code)),
        "expires_at": datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes
    }

    # Save to MongoDB (example: otp_collection)
    await otp_collection.insert_one(otp_data)
    try:
        send_watsapp_message(phone.phone,otp_code)
        print(f"OTP for {phone.phone} is {otp_code} (Simulated send via WhatsApp)")
        return JSONResponse(
        status_code=200,
        content={"message": f"OTP sent to {phone.phone} via WhatsApp"}
    )
    except:
        return JSONResponse(status_code=500, context={"message":"Internal server err watsapp issue"})


# Send OTP to the user
@app.post("/student/send_otp_sms")
async def send_otp_sms(phone: Send_Otp_Number):
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    # Generate 6-digit OTP
    otp_code = random.randint(100000, 999999)

    otp_data = {
        "phone": phone.phone,
        "otp": encode_base64(str(otp_code)),
        "expires_at": datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes
    }

    # Save to MongoDB (example: otp_collection)
    await otp_collection.insert_one(otp_data)
    try:
        send_sms_message(phone.phone,otp_code)
        print(f"✅ OTP for {phone.phone} is {otp_code} (Simulated send via SMS)")
        return JSONResponse(
        status_code=200,
        content={"message": f"✅ OTP sent to {phone.phone} via SMS"}
    )
    except:
        return JSONResponse(status_code=500, context={"message":"Internal server err watsapp issue"})



@app.post("/student/verify-otp")
async def verify_otp(veryfy_otp:Veryfy_OTP):
    if not veryfy_otp.phone or not veryfy_otp.otp:
        raise HTTPException(status_code=400, detail="Phone and OTP are required")

    otp_record = await otp_collection.find_one({"phone": veryfy_otp.phone, "otp": encode_base64(veryfy_otp.otp)})

    if not otp_record:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    if otp_record["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="OTP has expired")

    # Clean up OTP record after successful verification
    await otp_collection.delete_one({"_id": otp_record["_id"]})

    student = await profile_collection.find_one({"phone": veryfy_otp.phone})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student["_id"] = str(student["_id"])

    return JSONResponse(
        status_code=200,
        content={
            "message": "Login successful",
            "student": student
        }
    )


# Download - Resume
@app.post("/download-resume")
async def download_resume(payload: DownloadResume):
    student_id = payload.student_id
    print(student_id, "student_id")
    profile = await profile_collection.find_one({"student_id": student_id})

    print(profile, "profile")
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get the resume Base64 data
    resume_base64 = profile.get("resume_name")
    if not resume_base64:
        raise HTTPException(status_code=404, detail="Resume not found for this profile")

    # Decode Base64 to binary
    try:
        resume_bytes = base64.b64decode(resume_base64)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode resume: {str(e)}")

    # Return PDF file as response
    return StreamingResponse(
        io.BytesIO(resume_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={profile.get('full_name', 'resume')}.pdf"}
    )



# Admin - Login
@app.post("/admin_login")
async def admin_login(admin: Admin):
    if not admin.email or not admin.password:
        raise HTTPException(status_code=400, detail="email or password missing.")

    admin_user = await admin_collection.find_one({"email": admin.email})

    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    if admin.password != admin_user.get("password"):
        raise HTTPException(status_code=401, detail="Invalid password.")

    # Convert MongoDB ObjectId to str
    admin_user["_id"] = str(admin_user["_id"])


    admin_user.pop("password", None)
    
    token_data = {
        "sub": admin_user["_id"],
        "email": admin.email
    }
    access_token = create_access_token(data=token_data)

    return JSONResponse(
        status_code=200,
        content={
            "message": "Successfully logged in.",
            "access_token": access_token,
            "token_expire_minute": ACCESS_TOKEN_EXPIRE_MINUTES,
            "token_type": "bearer",
            "admin_data": admin_user
        }
    )



# Include authentication routes
app.include_router(auth_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)