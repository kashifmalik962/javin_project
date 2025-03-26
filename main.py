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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from auth.auth_linkedin import router as linkedin_router
from auth.auth_google import router as google_router
import re

# Load environment variables
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")


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
    sub_student_profiles = database["sub_student_profiles"]
    otp_collection = database["otp_collection"]
    admin_collection = database["admin"]
    # Activity - Path - Module
    activity_path_collection = database["activity_path_collection"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB. Error: {e}")



# Register - User
@app.post("/register_student")
async def register_student(student: RegisterStudent):
    try:
        if await profile_collection.find_one({"$or": [{"email": student.email}, {"phone": student.phone}]}):
            # raise HTTPException(status_code=409, detail="student already exists.")
            return JSONResponse(status_code=409, content={
            "message": f"student already exists.",
            "status_code":0
            })
        

        last_student = await profile_collection.find_one({}, sort=[("student_id", -1)])
        student_id = 101 if last_student is None else last_student["student_id"] + 1

        # Convert Pydantic model to dictionary
        student_data = student.model_dump()
        student_data["student_id"] = student_id
        student_data["is_kids"] = student_id

        print(student_data, "student_data +++++++++")
        result = await profile_collection.insert_one(student_data)
        inserted_id = result.inserted_id

        print(inserted_id, "inserted_id +++++++++")
        created_profile = await profile_collection.find_one({"_id": inserted_id}, {"_id": 0})

        print(created_profile, "created_profile +++++++++")
        return JSONResponse(status_code=201, content={
            "message": "Successfully Registered Student.",
            "status_code":1,
            "data": created_profile
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Failed to register {e}",
            "status_code":0
        })
        # raise HTTPException(status_code=500, message=f"Internal server {e}")


# Login - Student 
@app.post("/login_student")
async def login_student(login_student:LoginStudent):
    try:
        print(login_student, "login_student")
        profile_details =  await profile_collection.find_one(
            {"email":login_student.email, "phone":login_student.phone},
            {"_id": 0, "email":1, "phone":1})
        
        print(profile_details, "profile_details ----->")
        if not profile_details:
            # raise HTTPException(status_code=404, detail="student does not exists.")
            return JSONResponse(status_code=404, content={
                "message": "student does not exists.",
                "status_code": 0
            })

        
        print(profile_details, "profile_details")

        token_data = {
            "sub": profile_details["email"],
            "student_id": profile_details.get("student_id"),
            "phone": profile_details["phone"]
        }

        access_token = create_access_token(data=token_data)
        
        return JSONResponse(status_code=200, content={
            "message": "Successfully logged in.",
            "status_code": 1,
            "access_token": access_token,
            "token_expire_minute": ACCESS_TOKEN_EXPIRE_MINUTES,
            "token_type": "bearer",
            "data": profile_details
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error {e}",
            "status_code": 0
        })


# GET - STUDENT DETAILS
@app.get("/get_student/{student_id}")
async def get_student(student_id: int):
    student_details = await profile_collection.find_one({"student_id":student_id}, {"_id": 0, "resume_name":0})

    if not student_details:
        return JSONResponse(status_code=404, content={
            "message": "students does not exists.",
            "status_code": 0
        })
        # raise HTTPException(status_code=404, detail="students does not exists.")

    return JSONResponse(status_code=200, content={
        "message": "successfully data recieved.",
        "status_code": 1,
        "data": student_details
    })


# GET ALL SUB - STUDENTS
@app.get("/student_get_all_sub_student/{student_id}")
async def student_get_all_sub_student(student_id: int):
    try:
        sub_student_records = []

        # Find parent student
        profile_data = await profile_collection.find_one({"student_id": student_id}, {"resume_name":0})
        if not profile_data:
            # raise HTTPException(status_code=404, detail="Student does not exist.")
            return JSONResponse(status_code=404, content={
                "message": "Student does not exist.",
                "status_code": 0
            })

        # Convert `_id` to string
        profile_data["_id"] = str(profile_data["_id"])

        # Get sub_student_ids list
        sub_student_ids = profile_data.get("sub_student_id", [])
        
        print(sub_student_ids, "sub_student_ids")
        if not sub_student_ids:  # Check if the list is empty
            return JSONResponse(status_code=200, content={
                "message": "No sub-students assigned.",
                "data": profile_data,
                "status_code":1
            })

        # Fetch all sub-student records
        for sub_student_id in range(len(sub_student_ids)):
            sub_student_itr = await sub_student_profiles.find_one(
                {"student_id": sub_student_ids[sub_student_id]},
                {"resume_name":0}
                )

            if sub_student_itr:
                sub_student_itr["_id"] = str(sub_student_itr["_id"])  # Convert ObjectId to string
                sub_student_records.append(sub_student_itr)

        profile_data["sub_student_records"] = sub_student_records  # Store fetched records

        return JSONResponse(status_code=200, content={
            "message": "Successfully retrieved data.",
            "data": profile_data,
            "status_code": 1
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Error retrieving sub-students: {str(e)}",
            "status_code": 0
            })


# UPDATE STUDENT DATA
@app.put("/update_user/{student_id}")
@app.patch("/update_user/{student_id}")
async def update_user(student_id: int, request: Request):
    try:
        profile_updates: Dict[str, Any] = await request.json()  # Convert JSON to dict

        # Prevent updating restricted fields
        if "student_id" in profile_updates:
            # raise HTTPException(status_code=401, detail="student_id cannot be updated")
            return JSONResponse(status_code=401, content={
                "message": "student_id cannot be updated.",
                "status_code": 0
            })

        if not profile_updates:
            # raise HTTPException(status_code=400, detail="Request body cannot be empty.")
            return JSONResponse(status_code=400, content={
                "message": "Request body cannot be empty.",
                "status_code": 0
            })

        print(profile_updates, "profile_updates")

        # Check if the user exists
        existing_user = await profile_collection.find_one({"student_id": student_id})
        if not existing_user:
            # raise HTTPException(status_code=404, detail="User does not exist!")
            return JSONResponse(status_code=404, content={
                "message": "User does not exist!.",
                "status_code": 0
            })
            
        if request.method == "PATCH":
            # Remove fields with `None` values for PATCH (ignores missing fields)
            profile_updates = {k: v for k, v in profile_updates.items() if v is not None}

            if not profile_updates:  # If no valid fields remain
                # raise HTTPException(status_code=400, detail="No valid fields provided for update.")
                return JSONResponse(status_code=400, content={
                    "message": "No valid fields provided for update.",
                    "status_code": 0
                })

        # Update only the provided fields
        result = await profile_collection.update_one(
            {"student_id": student_id},
            {"$set": profile_updates}
        )

        if result.modified_count == 0:
            # raise HTTPException(status_code=400, detail="No changes made to the profile.")
            return JSONResponse(status_code=400, content={
                "message": "No changes made to the profile.",
                "status_code": 0
            })

        # Fetch updated user data
        updated_user = await profile_collection.find_one({"student_id": student_id}, {"_id": 0})

        return JSONResponse(status_code=200, content={
            "message": "Profile updated successfully!",
            "status_code": 1,
            "profile": updated_user
            }
        )

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Error updating profile: {str(e)}",
            "status_code": 0
            })



# Send OTP to the user
@app.post("/student/send_otp_watsapp")
async def send_otp_watsapp(phone: Send_Otp_Number):
    try:
        phone_number = phone.phone.strip()  # Remove spaces

        # Ensure phone number is not empty
        if not phone_number:
            return JSONResponse(status_code=400, content={
                "message": "Phone number is required.",
                "status_code": 0
            })

        # Regex pattern to extract country code and local number
        phone_pattern = re.compile(r"^\+?(\d{1,4})?(\d{10})$")  

        match = phone_pattern.match(phone_number)
        if not match:
            return JSONResponse(status_code=400, content={
                "message": "Invalid phone number format. Use correct format (e.g., +919149076448 or +9149076448).",
                "status_code": 0
            })

        country_code, local_number = match.groups()  

        # Ensure correct local number extraction
        final_number = local_number if not country_code or country_code == "91" else phone_number[len(country_code) + 1:]

        # Generate 6-digit OTP
        otp_code = random.randint(100000, 999999)

        otp_data = {
            "phone": final_number,  # Store only the correct local number
            "otp": encode_base64(str(otp_code)),
            "expires_at": datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes
        }

        # Save to MongoDB
        await otp_collection.insert_one(otp_data)
        
        try:
            send_watsapp_message(final_number, otp_code)  # Send only local number
            return JSONResponse(status_code=200, content={
                "message": f"OTP sent to {final_number} via WhatsApp",
                "status_code": 1
            })
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "message": f"Internal server error with WhatsApp service: {e}",
                "status_code": 0
            })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error: {e}",
            "status_code": 0
        })
    


# Send OTP to the user
@app.post("/student/send_otp_sms")
async def send_otp_sms(phone: Send_Otp_Number):
    try:
        phone_number = phone.phone.strip()  # Remove spaces

        # Ensure phone number is not empty
        if not phone_number:
            return JSONResponse(status_code=400, content={
                "message": "Phone number is required.",
                "status_code": 0
            })

        # Regex pattern to capture optional country code and 10-digit local number
        phone_pattern = re.compile(r"^\+?(\d{1,4})?(\d{10})$")  

        match = phone_pattern.match(phone_number)
        if not match:
            return JSONResponse(status_code=400, content={
                "message": "Invalid phone number format. Use correct format (e.g., +919149076448 or +9149076448).",
                "status_code": 0
            })

        country_code, local_number = match.groups()  # Extract country code and local number

        # If country code is missing, assume it's an Indian number
        if not country_code or country_code == "91":
            final_number = local_number
        else:
            final_number = phone_number[len(country_code) + 1:]  # Generic case for other country codes

        # Generate 6-digit OTP
        otp_code = random.randint(100000, 999999)

        otp_data = {
            "phone": final_number,  # Store only the correct local number
            "otp": encode_base64(str(otp_code)),
            "expires_at": datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes
        }

        # Save to MongoDB (example: otp_collection)
        await otp_collection.insert_one(otp_data)
        
        try:
            send_sms_message(final_number, otp_code)  # Send only local number
            return JSONResponse(status_code=200, content={
                "message": f"OTP sent to {final_number} via SMS",
                "status_code": 1
            })
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "message": f"Internal server error with SMS service: {e}",
                "status_code": 0
            })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error: {e}",
            "status_code": 0
        })


@app.post("/student/verify-otp")
async def verify_otp(veryfy_otp: Veryfy_OTP):
    try:
        if not veryfy_otp.phone or not veryfy_otp.otp:
            return JSONResponse(status_code=400, content={
                "message": "Phone and OTP are required",
                "status_code": 0
            })

        phone_number = veryfy_otp.phone.strip()

        # Regex pattern to extract country code and local number
        phone_pattern = re.compile(r"^\+?(\d{1,4})?(\d{10})$")  
        match = phone_pattern.match(phone_number)
        if not match:
            return JSONResponse(status_code=400, content={
                "message": "Invalid phone number format.",
                "status_code": 0
            })

        country_code, local_number = match.groups()
        final_number = local_number if not country_code or country_code == "91" else phone_number[len(country_code) + 1:]

        # Find OTP record in database
        otp_record = await otp_collection.find_one({"phone": final_number, "otp": encode_base64(veryfy_otp.otp)})

        if not otp_record:
            return JSONResponse(status_code=401, content={
                "message": "Invalid OTP",
                "status_code": 0
            })

        if otp_record["expires_at"] < datetime.utcnow():
            return JSONResponse(status_code=401, content={
                "message": "OTP has expired",
                "status_code": 0
            })

        # Remove OTP from database after successful verification
        await otp_collection.delete_one({"_id": otp_record["_id"]})

        return JSONResponse(status_code=200, content={
            "message": "Login successful",
            "status_code": 1
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error: {e}",
            "status_code": 0
        })


# Download - Resume
@app.post("/download-resume")
async def download_resume(payload: DownloadResume):
    try:
        student_id = payload.student_id
        print(student_id, "student_id")
        profile = await profile_collection.find_one({"student_id": student_id})

        print(profile, "profile")
        if not profile:
            # raise HTTPException(status_code=404, detail="Profile not found")
            return JSONResponse(status_code=404, content={
                "message": "Profile not found",
                "status_code": 0
            })

        # Get the resume Base64 data
        resume_base64 = profile.get("resume_name")
        if not resume_base64:
            # raise HTTPException(status_code=404, detail="Resume not found for this profile")
            return JSONResponse(status_code=404, content={
                "message": "Resume not found for this profile.",
                "status_code": 0
            })

        # Decode Base64 to binary
        try:
            resume_bytes = base64.b64decode(resume_base64)
        except Exception as e:
            # raise HTTPException(status_code=500, detail=f"Failed to decode resume: {str(e)}")
            return JSONResponse(status_code=500, content={
                "message": f"Failed to decode resume: {str(e)}.",
                "status_code": 0
            })

        # Return PDF file as response
        return StreamingResponse(
            io.BytesIO(resume_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={profile.get('full_name', 'resume')}.pdf"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={
                "message": f"Internal server error: {str(e)}.",
                "status_code": 0
            })


# Admin - Login
@app.post("/admin_login")
async def admin_login(admin: Admin):
    try:
        if not admin.email or not admin.password:
            # raise HTTPException(status_code=400, detail="email or password missing.")
            return JSONResponse(status_code=400, content={
                "message": "email or password missing.",
                "status_code": 0
            })

        admin_user = await admin_collection.find_one({"email": admin.email})

        if not admin_user:
            # raise HTTPException(status_code=404, detail="Admin user not found.")
            return JSONResponse(status_code=404, content={
                "message": "Admin user not found.",
                "status_code": 0
            })

        if admin.password != admin_user.get("password"):
            # raise HTTPException(status_code=401, detail="Invalid password.")
            return JSONResponse(status_code=401, content={
                "message": "Invalid password.",
                "status_code": 0
            })

        # Convert MongoDB ObjectId to str
        admin_user["_id"] = str(admin_user["_id"])


        admin_user.pop("password", None)
        
        token_data = {
            "sub": admin_user["_id"],
            "email": admin.email
        }
        access_token = create_access_token(data=token_data)

        return JSONResponse(status_code=200, content={
                "message": "Successfully logged in.",
                "status_code": 1,
                "access_token": access_token,
                "token_expire_minute": ACCESS_TOKEN_EXPIRE_MINUTES,
                "token_type": "bearer",
                "admin_data": admin_user
            }
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={
                "message": f"Internal server error {e}",
                "status_code": 0
        })


# REGISTER - SUB - STUDENT
@app.post("/register_sub_student")
async def register_sub_student(register_sub_student: RegisterSubStudent):
    try:
        if await sub_student_profiles.find_one({"$or": [{"email": register_sub_student.email}, {"phone": register_sub_student.phone}]}):
            # raise HTTPException(status_code=409, detail="sub student already exists.")
            return JSONResponse(status_code=409, content={
                "message": "sub student already exists.",
                "status_code": 0
            })
        
        parent_data = await profile_collection.find_one({"student_id": register_sub_student.parent_id})
        if not parent_data:
            # raise HTTPException(status_code=404, detail="Parent student does not exist.")
            return JSONResponse(status_code=404, content={
                "message": "Parent student does not exist.",
                "status_code": 0
            })

        # Generate new student_id
        last_student = await sub_student_profiles.find_one({}, sort=[("student_id", -1)])
        student_id = 1001 if last_student is None else last_student["student_id"] + 1

        try:
            # Append new student_id to parent's sub_student_id list
            await profile_collection.update_one(
                {"student_id": register_sub_student.parent_id},
                {"$push": {"sub_student_id": student_id}}
            )
        except Exception as e:
            # raise HTTPException(status_code=404, detail="Failed to update parent profile.")
            return JSONResponse(status_code=404, content={
                "message": "Failed to update parent profile.",
                "status_code": 0
            })

        # Convert Pydantic model to dictionary
        student_data = register_sub_student.model_dump()
        student_data["student_id"] = student_id
        
        print(student_data, "student_data +++++++++")
        result = await sub_student_profiles.insert_one(student_data)
        inserted_id = result.inserted_id
        
        print(inserted_id, "inserted_id +++++++++")
        created_profile = await sub_student_profiles.find_one({"_id": inserted_id}, {"_id": 0})

        print(created_profile, "created_profile +++++++++")
        return JSONResponse(status_code=201, content={
            "message": "Successfully Registered Student.",
            "status_code": 1,
            "data": created_profile
        })
    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"Internal server {e}")
        return JSONResponse(status_code=500, content={
            "message": f"Internal server {e}",
            "status_code": 0
        })


# GET - SUB - STUDENT DETAILS
@app.get("/get_sub_student/{student_id}")
async def get_sub_student(student_id: int):
    try:
        student_details = await sub_student_profiles.find_one({"student_id":student_id}, {"_id": 0, "resume_name":0})

        if not student_details:
            # raise HTTPException(status_code=404, detail="students does not exists.")
            return JSONResponse(status_code=404, content={
                    "message": "students does not exists.",
                    "status_code": 0
            })

        return JSONResponse(status_code=200, content={
            "message": "successfully data recieved.",
            "status_code": 1,
            "data": student_details
        })
    
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error {e}",
            "status_code": 0
        })


# SUB - STUDENT - UPDATE
@app.put("/sub_student_update_user/{student_id}")
@app.patch("/sub_student_update_user/{student_id}")
async def sub_student_update_user(student_id: int, request: Request):
    try:
        profile_updates: Dict[str, Any] = await request.json()  # Convert JSON to dict
        
        # Prevent updating restricted fields
        if "parent_id" in profile_updates or "student_id" in profile_updates:
            # raise HTTPException(status_code=401, detail="parent_id or student_id cannot be updated")
            return JSONResponse(status_code=401, content={
                "message": "parent_id or student_id cannot be updated",
                "status_code": 0
            })

        if not profile_updates:
            # raise HTTPException(status_code=400, detail="Request body cannot be empty.")
            return JSONResponse(status_code=400, content={
                "message": "Request body cannot be empty.",
                "status_code": 0
            })

        print(profile_updates, "profile_updates")

        # Check if the user exists
        existing_user = await sub_student_profiles.find_one({"student_id": student_id})
        if not existing_user:
            # raise HTTPException(status_code=404, detail="User does not exist!")
            return JSONResponse(status_code=404, content={
                "message": "User does not exist!",
                "status_code": 0
            })

        # Convert ObjectId to string
        existing_user["_id"] = str(existing_user["_id"])

        if request.method == "PATCH":
            # Remove fields with `None` values for PATCH (ignores missing fields)
            profile_updates = {k: v for k, v in profile_updates.items() if v is not None}

            # Ensure at least one field is different before updating
            actual_updates = {k: v for k, v in profile_updates.items() if existing_user.get(k) != v}
            
            if not actual_updates:  
                return JSONResponse(status_code=200, content={
                    "message": "No changes detected. Profile remains the same.",
                    "status_code":1,
                    "profile": existing_user
                })
        else:
            actual_updates = profile_updates  # PUT replaces entire document

        # Update only the provided fields
        result = await sub_student_profiles.update_one(
            {"student_id": student_id},
            {"$set": actual_updates}
        )

        if result.modified_count == 0:
            return JSONResponse(status_code=200, content={
                "message": "Profile update request received, but no changes were needed.",
                "status_code": 1,
                "profile": existing_user
            })

        # Fetch updated user data
        updated_user = await sub_student_profiles.find_one({"student_id": student_id})
        
        if updated_user:
            updated_user["_id"] = str(updated_user["_id"])  # Convert ObjectId to string

        return JSONResponse(status_code=200, content={
            "message": "Profile updated successfully!",
            "status_code": 1,
            "profile": updated_user
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "detail": f"Error updating profile: {str(e)}",
            "status_code":0
        })



                                # ACTIVITY PATH MODULE

@app.post("/activity_path_module")
async def create_activity(activity_path: ActivityPathModule):
    try:
        if await activity_path_collection.find_one(
            {"$or": [
                {"question": activity_path.question}
                ]
            }):
            # raise HTTPException(status_code=409, detail="question already exists.")
            return JSONResponse(status_code=409, content={
                "message": "question already exists.",
                "status_code": 0
            })
        
        # Get the last unique_id
        last_unique = await activity_path_collection.find_one({}, sort=[("unique_id", -1)])
        unique_id = 101 if last_unique is None else last_unique["unique_id"] + 1

        # Convert Pydantic model to dictionary
        activity_path_data = activity_path.model_dump()
        activity_path_data["unique_id"] = unique_id

        # Insert into MongoDB
        result = await activity_path_collection.insert_one(activity_path_data)
        inserted_id = result.inserted_id

        # Retrieve the inserted document
        created_profile = await activity_path_collection.find_one({"_id": inserted_id}, {"_id": 0})

        return JSONResponse(status_code=200, content={
            "message": "Successfully submitted data",
            "status_code": 1,
            "data": created_profile
        })
    
    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
        return JSONResponse(status_code=500, content={
            "message": f"Internal server error: {e}",
            "status_code": 0
        })




# Register Routers
app.include_router(linkedin_router)
app.include_router(google_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)