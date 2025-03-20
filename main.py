from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional
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


# Load environment variables
load_dotenv()

app = FastAPI()

# MongoDB connection
MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb+srv://kashifmalik962:gYxgUGO6622a1cRr@cluster0.aad1d.mongodb.net/node_mongo_crud?")
DATABASE_NAME = os.getenv("DATABASE_NAME", "student_profile")
PORT = int(os.getenv("PORT", 8000))


try:
    client = MongoClient(MONGO_DETAILS)
    database = client[DATABASE_NAME]
    fs = gridfs.GridFS(database)
    profile_collection = database["profiles"]
    otp_collection = database["otp_collection"]
    admin_collection = database["admin"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB. Error: {e}")



# Register - Student
@app.post("/register_user")
# async def register_user(profile: Profile):
#     print("Register user endpoint triggered...")

#     profile_data = profile.dict()

#     if profile.resume:
#         try:
#             # ✅ Decode Base64 resume
#             resume_bytes = base64.b64decode(profile.resume)
#             file_id = fs.put(resume_bytes, filename="resume.pdf", content_type="application/pdf")
#             print(f"✅ Resume saved to GridFS: {file_id}")
#             profile_data["resume_file_id"] = str(file_id)
#             del profile_data["resume"]  # ✅ Remove base64 string after storing
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error saving resume: {str(e)}")

#     try:
#         result = profile_collection.insert_one(profile_data)
#         print(f"✅ Inserted ID: {result.inserted_id}")

#         created_profile = profile_collection.find_one({"_id": result.inserted_id})

#         if created_profile:
#             created_profile["_id"] = str(created_profile["_id"])
#             if "resume_file_id" in created_profile:
#                 created_profile["resume_file_id"] = str(created_profile["resume_file_id"])

#             return {
#                 "message": "Profile created successfully with resume stored in GridFS!",
#                 "profile": created_profile
#             }
#         else:
#             raise HTTPException(status_code=500, detail="Profile not found after insert")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error inserting profile: {str(e)}")
@app.post("/register_user")
async def register_user(profile: Profile):
    try:
        profile_data = profile.dict()

        # Insert into MongoDB
        result = profile_collection.insert_one(profile_data)
        profile_data["_id"] = str(result.inserted_id)

        return JSONResponse(
            status_code=201,
            content={
                "message": "Profile created successfully!",
                "profile": profile_data
            }
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Error inserting profile: {str(e)}"})
    

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
    otp_collection.insert_one(otp_data)
    try:
        send_watsapp_message(phone.phone,otp_code)
        print(f"✅ OTP for {phone.phone} is {otp_code} (Simulated send via WhatsApp)")
        return JSONResponse(
        status_code=200,
        content={"message": f"✅ OTP sent to {phone.phone} via WhatsApp"}
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
    otp_collection.insert_one(otp_data)
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

    otp_record = otp_collection.find_one({"phone": veryfy_otp.phone, "otp": encode_base64(veryfy_otp.otp)})

    if not otp_record:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    if otp_record["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="OTP has expired")

    # Clean up OTP record after successful verification
    otp_collection.delete_one({"_id": otp_record["_id"]})

    student = profile_collection.find_one({"phone": veryfy_otp.phone})
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
@app.get("/download-resume/{profile_id}")
async def download_resume(profile_id: str):
    try:
        obj_id = ObjectId(profile_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid profile_id. Must be a valid ObjectId.")

    profile = profile_collection.find_one({"_id": obj_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    resume_file_id = profile.get("resume_file_id")
    if not resume_file_id:
        raise HTTPException(status_code=404, detail="Resume not found for this profile")

    try:
        grid_out = fs.get(ObjectId(resume_file_id))
        return StreamingResponse(
            io.BytesIO(grid_out.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={grid_out.filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving resume: {str(e)}")


# Admin - Login
@app.post("/admin_login")
async def admin_login(admin: Admin):

    if not admin.email or not admin.password:
        raise HTTPException(status_code=400, detail="email or password missing.")

    admin_user = admin_collection.find_one({"email": admin.email})

    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    if admin.password != admin_user.get("password"):
        raise HTTPException(status_code=401, detail="Invalid password.")

    # Success! You can return admin data (avoid returning passwords)
    admin_user["_id"] = str(admin_user["_id"])  # Convert ObjectId to string for JSON serialization
    admin_user.pop("password", None)  # Remove password before sending response

    return JSONResponse(
        status_code=200,
        content={
            "message": "✅ Successfully logged in.",
            "data": admin_user
        }
    )



if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
