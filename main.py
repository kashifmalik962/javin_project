from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse, FileResponse
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
from pymongo import DESCENDING
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlparse


# Load environment variables
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# MongoDB connection
MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb+srv://kashifmalik2786:BhWKQzVyaxRfzNti@cluster0.ctpzucp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "user_profile")
PORT = int(os.getenv("PORT", 8000))

UPLOAD_FOLDER = "static/resumes"
IMAGE_FOLDER = "static/images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Mount the static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    profile_collection = database["user_profiles"]
    # sub_user_profiles = database["sub_user_profiles"]
    otp_collection = database["otp_collection"]
    admin_collection = database["admin"]
    # Activity - Path - Module
    activity_path_collection = database["activity_path_collection"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB. Error: {e}")


# Custom Exception Handler for Validation Errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append(error["msg"])

    return JSONResponse(
        status_code=200,
        content={"message": errors[0], "status_code": 0},
    )

# Custom Exception Handler for HTTPException
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail, "status_code": 0},
    )

# Register - User
@app.post("/user")
async def register_user(user: RegisterUser, request: Request):
    try:
        data = await request.json()  # Debug incoming JSON data
        print(data, "Received JSON Data")  # Debug statement
        
        valid_phone = validation_number(user.phone)
        print(valid_phone, "valid_phone")

        # Check if user already exists
        existing_user = await profile_collection.find_one({
            "$or": [{"email": user.email}, {"email2": user.email},
                    {"phone": valid_phone}, {"phone2": valid_phone}]
        })
        if existing_user:
            return JSONResponse(status_code=200, content={
                "message": "user already exists.",
                "status_code": 0
            })

        # Generate new user ID
        last_user = await profile_collection.find_one({}, sort=[("user_id", DESCENDING)])
        user_id = 101 if last_user is None else last_user["user_id"] + 1

        user_data = user.model_dump()
        user_data["user_id"] = user_id
        user_data["profile_type"] = "primary"
        user_data["active"] = "true"

        # Fill missing fields with None
        default_fields = [
            "full_name", "email2", "phone2", "country", "address",
            "resume_name", "linkedin", "current_city", "preferred_city",
            "summary_of_profile", "college_background", "current_organization",
            "total_work_experience_years", "comment", "referred_by",
            "current_ctc", "desired_ctc", "github", "leetcode",
            "codechef", "sub_user_id", "picture"
        ]
        for field in default_fields:
            user_data.setdefault(field, None)

        token_data = {
            "user_id": user_data["user_id"],
            "email": user_data["email"]
        }

        access_token = create_access_token(data=token_data)

        # Insert user data
        result = await profile_collection.insert_one(user_data)
        inserted_id = result.inserted_id

        created_profile = await profile_collection.find_one({"_id": inserted_id}, {"_id": 0})

        # Profile Completeness in percentage
        rest_feilds = ["email", "phone", "sub_user_id", "referred_by", "profile_type", "active", "user_id"]
        number_of_fields = len(created_profile) - len(rest_feilds)
        print(created_profile, "created_profile")
        # null_fields = [key for key, value in created_profile.items() if value is None]
        null_fields = []
        for key, value in created_profile.items():
            if value is None and key not in rest_feilds:
                print(key, value, "key, value")
                null_fields.append(key)

        print(null_fields, "null_fields")
        print(number_of_fields, null_fields, "number_of_fields, null_fields")
        print(number_of_fields, len(null_fields), "number_of_fields, null_fields")
        print(100 - ((len(null_fields)/number_of_fields)*100))
        completeness_precent = 100 - ((len(null_fields)/number_of_fields)*100)
        update_profile_complete = await profile_collection.update_one(
            {"_id": inserted_id}, 
            {"$set": {"profile_complete": completeness_precent}}
        )

        # Fetch updated profile with profile completeness after the update
        updated_profile = await profile_collection.find_one({"_id": inserted_id}, {"_id": 0})

        return JSONResponse(status_code=200, content={
            "message": "Successfully Registered user.",
            "status_code": 1,
            "access_token": access_token,
            "token_expire_minute": USER_ACCESS_TOKEN_EXPIRE_MINUTES,
            "token_type": "bearer",
            "data": updated_profile
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=200, content={
            "message": f"Failed to register. {e}",
            "status_code": 0
        })

        # raise HTTPException(status_code=200, message=f"Internal server.")


# GET - user DETAILS
@app.get("/user/{user_id}")
async def get_user(user_id: int, request: Request):
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=200, detail="Authorization header missing")
        
        # Token is in the form: Bearer <token>
        token = auth_header.split(" ")[1] if " " in auth_header else None
        
        if not token:
            raise HTTPException(status_code=200, detail="Token is missing")
        
        # Validate the token
        payload = validate_token(token)

        user_details = await profile_collection.find_one({"user_id":user_id}, {"_id": 0})

        if not user_details:
            return JSONResponse(status_code=200, content={
                "message": "users does not exists.",
                "status_code": 0
            })
            # raise HTTPException(status_code=200, detail="users does not exists.")

        return JSONResponse(status_code=200, content={
            "message": "successfully data recieved.",
            "status_code": 1,
            "data": user_details
        })
    
    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions
    
    except Exception as e:
        return JSONResponse(status_code=200, content={
            "message": f"Internal server error. {e}",
            "status_code": 0
        })


# UPDATE user DATA
# @app.patch("/update_user/{user_id}")
@app.put("/user/{user_id}")
async def update_user(user_id: int, request: Request):
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=200, detail="Authorization header missing")
        
        # Token is in the form: Bearer <token>
        token = auth_header.split(" ")[1] if " " in auth_header else None
        
        if not token:
            raise HTTPException(status_code=200, detail="Token is missing")
        
        # Validate the token
        payload = validate_token(token)

        # Check if user exists
        exist_user = await profile_collection.find_one({"user_id": user_id})
        if not exist_user:
            return JSONResponse(status_code=200, content={
                "message": "user does not exist.",
                "status_code": 0
            })

        profile_updates: Dict[str, Any] = await request.json()  # Convert JSON to dict

        # Ensure the request body is not empty
        if not profile_updates:
            return JSONResponse(status_code=200, content={
                "message": "Request body cannot be empty.",
                "status_code": 0
            })
        
        # Handle Resume PDF
        update_changes = False
        if profile_updates.get("resume_name"):
            # full_name = profile_updates.get("full_name")
            base64_resume = profile_updates.get("resume_name")
            # Create a unique filename (e.g., kashif_malik_resume.pdf)
            filename = f"{user_id}_resume.pdf"

            # Save PDF from base64
            pdf_path = save_pdf_from_base64(base64_resume, filename, upload_folder=UPLOAD_FOLDER)

            # Generate public URL
            file_url = f"https://javin-project.onrender.com/static/resumes/{filename}"
            profile_updates["resume_name"] = file_url
            update_changes = True
        
        # Handle Image
        if profile_updates.get("picture"):
            base64_image = profile_updates.get("picture")
            image_filename = f"{user_id}_profile.jpg"
            img_path = save_image_from_base64(base64_image, image_filename, upload_folder=IMAGE_FOLDER)
            img_url = f"https://javin-project.onrender.com/static/images/{image_filename}"
            profile_updates["picture"] = img_url
            update_changes = True

        if profile_updates.get("email2") or profile_updates.get("phone2"):
            print("profile_updates.get(phone2)")
            # Get existing user details
            exist_user_email = exist_user.get("email") 
            exist_user_phone = exist_user.get("phone")

            # Get new updates
            new_email2 = profile_updates.get("email2")
            new_phone2 = profile_updates.get("phone2")

            
            try:
                # Validate email and phone
                # if new_email2:
                is_valid_email(new_email2)  # Validate email format
                # if new_phone2:
                    # print("validation_number")
                validation_number(new_phone2)  # Assuming validation_number is already implemented
            except HTTPException as e:
                # Handle validation errors
                return JSONResponse(status_code=200, content={
                    "message": "Invalid email and number format.",
                    "status_code": 0
                })

            # Prevent primary email or phone from being the same as secondary email or phone
            if new_email2 and exist_user_email == new_email2:
                return JSONResponse(status_code=200, content={
                    "message": "Secondary email cannot be the same as primary email.",
                    "status_code": 0
                })

            if new_phone2 and exist_user_phone == new_phone2:
                return JSONResponse(status_code=200, content={
                    "message": "Secondary phone cannot be the same as primary phone.",
                    "status_code": 0
                })


            # Check for duplicate email & phone in another user’s profile
            email2 = profile_updates.get("email2")
            phone2 = profile_updates.get("phone2")

            if email2 and phone2 and email2 == phone2:
                return JSONResponse(status_code=200, content={
                    "message": "Email2 and Phone2 cannot be the same.",
                    "status_code": 0
                })

            existing_user = await profile_collection.find_one({
                "$or": [
                    {"email": email2},
                    {"email2": email2},
                    {"phone": phone2},
                    {"phone2": phone2}
                ],
                "user_id": {"$ne": user_id}  # Exclude the current user
            })

            # print(existing_user, "existing_user")
            if existing_user:
                return JSONResponse(status_code=200, content={
                    "message": "Email2 or Phone2 is already attached to another account.",
                    "status_code": 0
                })
            
        
        # Prevent updating restricted fields
        restricted_fields = ["user_id", "email", "phone", "active", "profile_type", "profile_complete"]
        if any(field in profile_updates for field in restricted_fields):
            return JSONResponse(status_code=200, content={
                "message": "user_id, primary email, primary phone, active, profile_type, profile_complete cannot be updated.",
                "status_code": 0
            })
        
        # Update user profile
        result = await profile_collection.update_one(
            {"user_id": user_id},
            {"$set": profile_updates}
        )

        # Fetch updated user data
        created_profile = await profile_collection.find_one({"user_id": user_id}, {"_id": 0})
         # Profile Completeness in percentage
        number_of_fields = len(created_profile)
        rest_feilds = ["email", "phone", "sub_user_id", "referred_by", "profile_type", "active", "user_id"]
        number_of_fields = len(created_profile) - len(rest_feilds)
        print(number_of_fields, "number_of_fields")
        print(created_profile, "created_profile hai")
        # null_fields = [key for key, value in created_profile.items() if value is None]
        null_fields = []
        for key, value in created_profile.items():
            # print("loop..")
            if (value is None or value == "") and key not in rest_feilds:
                print(key, value, "key, value")
                null_fields.append(key)

        print(null_fields, "null_fields")
        completeness_precent = round(100 - ((len(null_fields)/number_of_fields)*100),2)

        profile_updates["profile_complete"] = completeness_precent
        update_profile_complete = await profile_collection.update_one(
            {"user_id": user_id},
            {"$set": profile_updates}
        )
        # if update_profile_complete.modified_count == 0 and update_changes!=True:
        #     return JSONResponse(status_code=200, content={
        #         "message": "No changes made to the profile.",
        #         "status_code": 0
        #     })
        
        # Fetch updated profile with profile completeness after the update
        updated_profile = await profile_collection.find_one({"user_id": user_id}, {"_id": 0})

        return JSONResponse(status_code=200, content={
            "message": "Profile updated successfully!",
            "status_code": 1,
            "profile": updated_profile
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions

    except Exception as e:
        print(f"Error updating profile: {str(e)}")  # Log error details
        return JSONResponse(status_code=200, content={
            "message": f"Internal server error while updating profile.",
            "status_code": 0
        })


# Delete user
@app.delete("/user/{user_id}")
async def delete_user(user_id: int, request: Request):
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=200, detail="Authorization header missing")
        
        # Token is in the form: Bearer <token>
        token = auth_header.split(" ")[1] if " " in auth_header else None
        
        if not token:
            raise HTTPException(status_code=200, detail="Token is missing")
        
        # Validate the token
        payload = validate_token(token)

        exist_user = await profile_collection.find_one({"user_id": user_id})
        if not exist_user:
            return JSONResponse(status_code=200, content={
                "message": "user does not exist.",
                "status_code": 0
            })
        
        try:
            print("in deleted try block")
            # Optional: Remove associated files (resume, image)
            profile_picture = exist_user.get("picture")
            profile_resume = exist_user.get("resume_name")
        
            def delete_file_if_exists(file_url: str):
                if not file_url:
                    return

                # Convert URL to file path
                parsed = urlparse(file_url)
                file_path = parsed.path.lstrip("/")  # Remove leading slash
        
                if os.path.exists(file_path):
                    print("Deleting:", file_path)
                    os.remove(file_path)
                else:
                    print("File does not exist:", file_path)
            

            print(profile_picture,"profile_picture")
            print(profile_resume, "profile_resume")
            delete_file_if_exists(profile_picture)
            delete_file_if_exists(profile_resume)
        except:
            pass

        await profile_collection.delete_one({"user_id": user_id})

        return JSONResponse(status_code=200, content={
            "message": "user deleted successfully.",
            "status_code": 1,
            "deleted_user_id": user_id  # Return deleted user_id
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions
    

    except Exception as e:
        return JSONResponse(status_code=200, content={
            "message": f"Internal server error while deleting user. {e}",
            "status_code": 0
        })



# REGISTER - SUB - user
@app.post("/user/register_sub_user")
async def register_sub_user(register_sub_user: RegisterSubUser, request:Request):
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=200, detail="Authorization header missing")
        
        # Token is in the form: Bearer <token>
        token = auth_header.split(" ")[1] if " " in auth_header else None
        
        if not token:
            raise HTTPException(status_code=200, detail="Token is missing")
        
        # Validate the token
        payload = validate_token(token)

        # Validate phone number
        valid_phone = validation_number(register_sub_user.phone)

        if await profile_collection.find_one({"$or": [{"email": register_sub_user.email}, {"phone": valid_phone}]}):
            # raise HTTPException(status_code=200, detail="sub user already exists.")
            return JSONResponse(status_code=200, content={
                "message": "sub user already exists.",
                "status_code": 0
            })
        
        parent_data = await profile_collection.find_one({"user_id": register_sub_user.parent_id})
        if not parent_data:
            # raise HTTPException(status_code=200, detail="Parent user does not exist.")
            return JSONResponse(status_code=200, content={
                "message": "Parent user does not exist.",
                "status_code": 0
            })        

        # Generate new user_id
        last_user = await profile_collection.find_one({}, sort=[("user_id", -1)])
        user_id = 1001 if last_user is None else last_user["user_id"] + 1

        # sub_user_ids = parent_data.get("sub_user_id")
        # if user_id in sub_user_ids:
        #     return JSONResponse(status_code=200, content={
        #         "message": "sub user already registered.",
        #         "status_code": 1
        #     })     

        try:
            print(register_sub_user.parent_id,"register_sub_user.parent_id")
            print(user_id, "user_id")
            if parent_data and parent_data.get("sub_user_id") is None:
                # If sub_user_id is null, set it to an empty list
                await profile_collection.update_one(
                    {"user_id": register_sub_user.parent_id},
                    {"$set": {"sub_user_id": []}}
                )
            # Append new user_id to parent's sub_user_id list
            await profile_collection.update_one(
                {"user_id": register_sub_user.parent_id},
                {"$push": {"sub_user_id": user_id}}
            )
        except Exception as e:
            # raise HTTPException(status_code=200, detail="Failed to update parent profile.")
            return JSONResponse(status_code=200, content={
                "message": "Failed to update parent profile.",
                "status_code": 0
            })

        # Convert Pydantic model to dictionary
        user_data = register_sub_user.model_dump()
        user_data["user_id"] = user_id
        user_data["phone"] = valid_phone
        user_data["profile_type"] = "secondary"
        
        print(user_data, "user_data +++++++++")
        result = await profile_collection.insert_one(user_data)
        inserted_id = result.inserted_id
        
        print(inserted_id, "inserted_id +++++++++")
        created_profile = await profile_collection.find_one({"_id": inserted_id}, {"_id": 0})

        return JSONResponse(status_code=200, content={
            "message": "Successfully Registered user.",
            "status_code": 1,
            "data": created_profile
        })
    
    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions
    
    except Exception as e:
        # raise HTTPException(status_code=200, detail=f"Internal server.")
        return JSONResponse(status_code=200, content={
            "message": f"Internal server.",
            "status_code": 0
        })



# Login - user 
# @app.post("/login_user")
# async def login_user(login_user:Loginuser):
#     try:
#         # Validate phone number
#         valid_phone = validation_number(login_user.phone)
#         # print(valid_phone, "valid_phone")

#         # print(login_user, "login_user")
#         profile_details =  await profile_collection.find_one(
#             {"email":login_user.email, "phone":valid_phone},
#             {"_id": 0, "resume_name":0}
#             )
        
#         # print(profile_details, "profile_details ----->")
#         if not profile_details:
#             # raise HTTPException(status_code=200, detail="user does not exists.")
#             return JSONResponse(status_code=200, content={
#                 "message": "user does not exists.",
#                 "status_code": 0
#             })

        
#         # print(profile_details, "profile_details")
            
#         token_data = {
#             "user_id": profile_details.get("user_id"),
#             "email": profile_details["email"]
#         }

#         access_token = create_access_token(data=token_data)
        
#         return JSONResponse(status_code=200, content={
#             "message": "Successfully logged in.",
#             "status_code": 1,
#             "access_token": access_token,
#             "token_expire_minute": user_ACCESS_TOKEN_EXPIRE_MINUTES,
#             "token_type": "bearer",
#             "data": profile_details
#         })
    
#     except Exception as e:
#         return JSONResponse(status_code=200, content={
#             "message": f"Internal server error.",
#             "status_code": 0
#         })




# Send OTP to the user
@app.post("/user/send_otp")
async def send_otp_whatsapp(phone: Send_Otp_Number):
    if phone.type == "whatsapp":
        try:
            print("IN whatsapp")
            phone_number = phone.phone.strip()  # Remove spaces

            # Ensure phone number is not empty
            if not phone_number:
                raise HTTPException(status_code=200, detail="Phone number is required.")

            # Regex pattern to extract country code and local number
            phone_pattern = re.compile(r"^\+?(\d{1,4})?(\d{10})$")

            match = phone_pattern.match(phone_number)
            if not match:
                raise HTTPException(
                    status_code=200,
                    detail="Invalid phone number format. Use correct format (e.g., +919149076448 or +9149076448)."
                )

            country_code, local_number = match.groups()

            # Ensure correct local number extraction
            final_number = local_number if not country_code or country_code == "91" else phone_number[len(country_code) + 1:]

            print(final_number, "final_number")
            # Check if phone number exists in the database
            user = await profile_collection.find_one({"phone": final_number, "profile_type": "primary"})
            if not user:
                raise HTTPException(status_code=200, detail="user Phone number not found.")

            user_active = user.get("active")
            if user_active != "true":
                raise HTTPException(status_code=200, detail="user Inactivated from Admin side.")
            
            # Generate 6-digit OTP
            otp_code = random.randint(100000, 999999)

            otp_data = {
                "phone": final_number,  # Store only the correct local number
                "otp": encode_base64(str(otp_code)),
                "expires_at": datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes
            }

            # Save to MongoDB
            await otp_collection.insert_one(otp_data)

            # Send OTP via WhatsApp
            try:
                send_whatsapp_message(final_number, otp_code)  # Send only local number
                return JSONResponse(status_code=200, content={
                    "message": f"OTP sent to {final_number} via WhatsApp",
                    "status_code": 1
                })
            except Exception as e:
                raise HTTPException(status_code=200, detail=f"Internal server error with WhatsApp service.")

        except HTTPException as e:
            raise e  # Rethrow FastAPI exceptions to be handled by the global exception handler
        except Exception as e:
            raise HTTPException(status_code=200, detail=f"Internal server error.")
    
    if phone.type == "sms":
        try:
            print("IN sms")
            # Validate phone number
            valid_phone = validation_number(phone.phone)

            # Check if phone number exists in the database
            number = await profile_collection.find_one({"phone": valid_phone, "profile_type": "primary"})
            if not number:
                raise HTTPException(status_code=200, detail="Phone number not found.")
            
            user_active = number.get("active")
            if user_active != "true":
                raise HTTPException(status_code=200, detail="user Inactivated from Admin side.")
            # Generate 6-digit OTP
            otp_code = random.randint(100000, 999999)

            otp_data = {
                "phone": valid_phone,  
                "otp": encode_base64(str(otp_code)),  # Store encoded OTP
                "expires_at": datetime.utcnow() + timedelta(minutes=5)  # Expiry in 5 minutes
            }

            # Delete old OTP (if exists) to avoid duplicates
            await otp_collection.delete_one({"phone": valid_phone})

            # Insert new OTP
            await otp_collection.insert_one(otp_data)

            # Send OTP via SMS
            try:
                send_sms_message(valid_phone, otp_code)  # Send only raw OTP
                return JSONResponse(status_code=200, content={
                    "message": f"OTP sent to {valid_phone} via SMS",
                    "status_code": 1
                })
            except Exception as e:
                raise HTTPException(status_code=200, detail=f"SMS sending failed.")

        except HTTPException as e:
            raise e  # Let FastAPI handle known exceptions
        except Exception as e:
            raise HTTPException(status_code=200, detail=f"Internal server error.")



# VERIFY - OTP
@app.post("/user/verify_otp")
async def verify_otp(verify_otp: Veryfy_OTP):
    try:
        if not verify_otp.phone or not verify_otp.otp:
            raise HTTPException(status_code=200, detail="Phone and OTP are required.")

        # Validate phone number format
        phone_number = validation_number(verify_otp.phone)

        # Encode OTP before searching
        encoded_otp = encode_base64(verify_otp.otp)

        # ✅ Fetch OTPs and sort manually if needed
        otp_records = await otp_collection.find({"phone": phone_number}).to_list(None)

        # ✅ Ensure correct sorting
        otp_records.sort(key=lambda x: x["expires_at"], reverse=True)  # Latest first

        # ✅ Get latest OTP record
        otp_record = otp_records[0] if otp_records else None

        print(otp_record, "otp_record")
        if not otp_record or otp_record["otp"] != encoded_otp:
            raise HTTPException(status_code=200, detail="Invalid OTP.")

        if otp_record["expires_at"] < datetime.utcnow():
            raise HTTPException(status_code=200, detail="OTP has expired.")

        # ✅ Remove ONLY the latest OTP after successful verification
        await otp_collection.delete_many({"phone": phone_number})

        # ✅ Fetch user profile (excluding _id)
        stu_profile = await profile_collection.find_one({"phone": phone_number}, {"_id": 0})
        
        token_data = {
            "user_id": stu_profile.get("user_id"),
            "email": stu_profile["email"]
        }

        access_token = create_access_token(data=token_data)
        
        return JSONResponse(status_code=200, content={
            "message": "Successfully logged in.",
            "status_code": 1,
            "access_token": access_token,
            "token_expire_minute": USER_ACCESS_TOKEN_EXPIRE_MINUTES,
            "token_type": "bearer",
            "data": stu_profile
        })

    except HTTPException as http_exc:
        return JSONResponse(status_code=http_exc.status_code, content={
            "message": http_exc.detail,
            "status_code": 0
        })
    except Exception as e:
        return JSONResponse(status_code=200, content={  # 200 for internal errors
            "message": f"Internal server error: {str(e)}",
            "status_code": 0
        })


# @app.post("/user/send_otp_sms")
# async def send_otp_sms(phone: Send_Otp_Number):
#     try:
#         # Validate phone number
#         valid_phone = validation_number(phone.phone)

#         # Check if phone number exists in the database
#         number = await profile_collection.find_one({"phone": valid_phone, "profile_type": "primary"})
#         if not number:
#             raise HTTPException(status_code=200, detail="Phone number not found.")
        
#         # Generate 6-digit OTP
#         otp_code = random.randint(100000, 999999)

#         otp_data = {
#             "phone": valid_phone,  
#             "otp": encode_base64(str(otp_code)),  # Store encoded OTP
#             "expires_at": datetime.utcnow() + timedelta(minutes=5)  # Expiry in 5 minutes
#         }

#         # Delete old OTP (if exists) to avoid duplicates
#         await otp_collection.delete_one({"phone": valid_phone})

#         # Insert new OTP
#         await otp_collection.insert_one(otp_data)

#         # Send OTP via SMS
#         try:
#             send_sms_message(valid_phone, otp_code)  # Send only raw OTP
#             return JSONResponse(status_code=200, content={
#                 "message": f"OTP sent to {valid_phone} via SMS",
#                 "status_code": 1
#             })
#         except Exception as e:
#             raise HTTPException(status_code=200, detail=f"SMS sending failed.")

#     except HTTPException as e:
#         raise e  # Let FastAPI handle known exceptions
#     except Exception as e:
#         raise HTTPException(status_code=200, detail=f"Internal server error.")




# Download - Resume
# @app.post("/download_resume")
# async def download_resume(payload: DownloadResume):
#     try:
#         user_id = payload.user_id
#         user = await profile_collection.find_one({"user_id": user_id})
    
#         if not user:
#             return JSONResponse(status_code=200, content={
#                 "message": "user not found.",
#                 "status_code": 0
#             })

#         resume_url = user.get("resume_name")
#         if not resume_url:
#             return JSONResponse(status_code=200, content={
#                 "message": "Resume not found.",
#                 "status_code": 0
#             })

#         filename = os.path.basename(resume_url)  # Extract filename safely
#         file_path = os.path.join("static/resumes", filename)

#         if not os.path.exists(file_path):
#             return JSONResponse(status_code=200, content={
#                 "message": "File does not exist.",
#                 "status_code": 0
#             })

#         return FileResponse(
#             file_path, 
#             media_type="application/pdf", 
#             filename=filename,
#             headers={"Content-Disposition": "attachment"}
#         )
    
#     except Exception as e:
#         print(f"Error downloading resume: {str(e)}")  # Log the error
#         return JSONResponse(status_code=200, content={
#             "message": "Internal server error.",
#             "status_code": 0
#         })




# # GET - SUB - user DETAILS  -- DUPLICATE
# @app.get("/get_sub_user/{user_id}")
# async def get_sub_user(user_id: int):
#     try:
#         user_details = await profile_collection.find_one(
#             {"$and": [{"user_id": user_id}, {"profile_type": "secondary"}]}, 
#             {"_id": 0, "resume_name": 0}
#         )

#         if not user_details:
#             # raise HTTPException(status_code=200, detail="users does not exists.")
#             return JSONResponse(status_code=200, content={
#                     "message": "users does not exists.",
#                     "status_code": 0
#             })
        
#         print(user_details, "user_details +++")
#         if not user_details.get("profile_type") == "primary":
#             return JSONResponse(status_code=200, content={
#                 "message": "successfully data recieved.",
#                 "status_code": 1,
#                 "data": user_details
#             })

#     except Exception as e:
#         return JSONResponse(status_code=200, content={
#             "message": f"Internal server error.",
#             "status_code": 0
#         })


# SUB - user - UPDATE
# @app.put("/update_sub_user/{user_id}")
# @app.patch("/update_sub_user/{user_id}")
# async def update_sub_user(user_id: int, request: Request):
#     try:
#         profile_updates: Dict[str, Any] = await request.json()  # Convert JSON to dict
        
#         # Prevent updating restricted fields
#         if "parent_id" in profile_updates or "user_id" in profile_updates:
#             # raise HTTPException(status_code=200, detail="parent_id or user_id cannot be updated")
#             return JSONResponse(status_code=200, content={
#                 "message": "parent_id or user_id cannot be updated",
#                 "status_code": 0
#             })

#         if not profile_updates:
#             # raise HTTPException(status_code=200, detail="Request body cannot be empty.")
#             return JSONResponse(status_code=200, content={
#                 "message": "Request body cannot be empty.",
#                 "status_code": 0
#             })

#         print(profile_updates, "profile_updates")

#         # Check if the user exists
#         existing_user = await profile_collection.find_one({"user_id": user_id})
#         if not existing_user:
#             # raise HTTPException(status_code=200, detail="User does not exist!")
#             return JSONResponse(status_code=200, content={
#                 "message": "User does not exist!",
#                 "status_code": 0
#             })

#         # Convert ObjectId to string
#         existing_user["_id"] = str(existing_user["_id"])

#         if request.method == "PATCH":
#             # Remove fields with `None` values for PATCH (ignores missing fields)
#             profile_updates = {k: v for k, v in profile_updates.items() if v is not None}

#             # Ensure at least one field is different before updating
#             actual_updates = {k: v for k, v in profile_updates.items() if existing_user.get(k) != v}
            
#             if not actual_updates:  
#                 return JSONResponse(status_code=200, content={
#                     "message": "No changes detected. Profile remains the same.",
#                     "status_code":1,
#                     "profile": existing_user
#                 })
#         else:
#             actual_updates = profile_updates  # PUT replaces entire document

#         # Update only the provided fields
#         result = await profile_collection.update_one(
#             {"user_id": user_id},
#             {"$set": actual_updates}
#         )

#         if result.modified_count == 0:
#             return JSONResponse(status_code=200, content={
#                 "message": "Profile update request received, but no changes were needed.",
#                 "status_code": 1,
#                 "profile": existing_user
#             })

#         # Fetch updated user data
#         updated_user = await profile_collection.find_one({"user_id": user_id})
        
#         if updated_user:
#             updated_user["_id"] = str(updated_user["_id"])  # Convert ObjectId to string

#         return JSONResponse(status_code=200, content={
#             "message": "Profile updated successfully!",
#             "status_code": 1,
#             "profile": updated_user
#         })

#     except HTTPException as http_exc:
#         raise http_exc  # Pass through FastAPI exceptions

#     except Exception as e:
#         return JSONResponse(status_code=200, content={
#             "detail": f"Error updating profile.",
#             "status_code":0
#         })



                                # ACTIVITY PATH MODULE

@app.post("/activity_path_module")
async def create_activity(activity_path: ActivityPathModule):
    try:
        if await activity_path_collection.find_one(
            {"$or": [
                {"question": activity_path.question}
                ]
            }):
            return JSONResponse(status_code=200, content={
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
        return JSONResponse(status_code=200, content={
            "message": f"Internal server error.",
            "status_code": 0
        })




                                        # Admin

# Admin - Login                                       
@app.post("/admin_login")
async def admin_login(admin: Admin):
    try:
        if not admin.email or not admin.password:
            # raise HTTPException(status_code=200, detail="email or password missing.")
            return JSONResponse(status_code=200, content={
                "message": "email or password missing.",
                "status_code": 0
            })

        admin_user = await admin_collection.find_one({"email": admin.email})

        if not admin_user:
            # raise HTTPException(status_code=200, detail="Admin user not found.")
            return JSONResponse(status_code=200, content={
                "message": "Admin user not found.",
                "status_code": 0
            })

        if admin.password != admin_user.get("password"):
            # raise HTTPException(status_code=200, detail="Invalid password.")
            return JSONResponse(status_code=200, content={
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
        access_token = create_access_token(data=token_data, type="admin")

        return JSONResponse(status_code=200, content={
                "message": "Successfully logged in.",
                "status_code": 1,
                "access_token": access_token,
                "token_expire_minute": ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES,
                "token_type": "bearer",
                "data": admin_user
            }
        )
    
    except HTTPException as http_exc:
        raise http_exc  # Pass through FastAPI exceptions
    
    except Exception as e:
        return JSONResponse(status_code=200, content={
                "message": f"Internal server error.",
                "status_code": 0
        })



# GET ALL SUB - userS
@app.get("/admin/get_all_sub_user/{user_id}")
async def get_all_sub_user(user_id: int, request: Request):
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(status_code=200, detail="Authorization header missing")
        
        # Token is in the form: Bearer <token>
        token = auth_header.split(" ")[1] if " " in auth_header else None
        
        if not token:
            raise HTTPException(status_code=200, detail="Token is missing")
        
        # Validate the token
        payload = validate_token(token)

        sub_user_records = []

        # Find parent user
        profile_data = await profile_collection.find_one({"user_id": user_id})
        if not profile_data:
            # raise HTTPException(status_code=200, detail="user does not exist.")
            return JSONResponse(status_code=200, content={
                "message": "user does not exist.",
                "status_code": 0
            })

        profile_type = profile_data.get("profile_type", "primary")
        if profile_type == "secondary":
            print("secondary")
            return JSONResponse(status_code=200, content={
                "message": "user does not exist.",
                "status_code": 0
            })
        
        # Convert `_id` to string
        profile_data["_id"] = str(profile_data["_id"])

        # Get sub_user_ids list
        sub_user_ids = profile_data.get("sub_user_id", [])
        
        print(sub_user_ids, "sub_user_ids")
        if not sub_user_ids:  # Check if the list is empty
            return JSONResponse(status_code=200, content={
                "message": "No sub-users assigned.",
                "data": profile_data,
                "status_code":1
            })

        # Fetch all sub-user records
        for sub_user_id in range(len(sub_user_ids)):
            sub_user_itr = await profile_collection.find_one(
                {"user_id": sub_user_ids[sub_user_id]})

            if sub_user_itr:
                sub_user_itr["_id"] = str(sub_user_itr["_id"])  # Convert ObjectId to string
                sub_user_records.append(sub_user_itr)

        profile_data["sub_user_records"] = sub_user_records  # Store fetched records

        return JSONResponse(status_code=200, content={
            "message": "Successfully retrieved data.",
            "data": profile_data,
            "status_code": 1
        })

    except HTTPException as http_exc:
        raise http_exc  # Pass FastAPI exceptions

    except Exception as e:
        return JSONResponse(status_code=200, content={
            "message": f"Error retrieving sub-users.",
            "status_code": 0
            })


# GET ALL REGISTER user
@app.get("/admin/get_all_register_user")
async def get_all_register_user(request: Request):
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(status_code=200, detail="Authorization header missing")
    
    # Token is in the form: Bearer <token>
    token = auth_header.split(" ")[1] if " " in auth_header else None
    
    if not token:
        raise HTTPException(status_code=200, detail="Token is missing")
    
    # Validate the token
    payload = validate_token(token)
    
    try:
        # Fetch all users from the database
        all_users = await profile_collection.find({}, {"_id": 0}).to_list(None)

        if all_users:
            return JSONResponse(status_code=200, content={
                "message": "Successfully retrieved data.",
                "status_code": 1,
                "total_user": len(all_users),
                "data": all_users
            })
        else:
            return JSONResponse(status_code=200, content={
                "message": "No users found.",
                "status_code": 1,
                "total_user": len(all_users),
                "data": all_users
            })

    except HTTPException as http_exc:
        raise http_exc  # Pass FastAPI exceptions
    
    except Exception as e:
        # Log the error and return an internal server error response
        return JSONResponse(status_code=200, content={
            "message": "Internal server error.",
            "status_code": 0
        })
    

@app.post("/admin/account_active/{user_id}")
async def change_user_activity(user_id: int, ChangeuserActive:ChangeUserActive, request:Request):
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(status_code=200, detail="Authorization header missing")
    
    # Token is in the form: Bearer <token>
    token = auth_header.split(" ")[1] if " " in auth_header else None
    
    if not token:
        raise HTTPException(status_code=200, detail="Token is missing")
    
    # Validate the token
    payload = validate_token(token)

    try:
        exist_user = await profile_collection.find_one({"user_id": user_id}, {"_id":0})
        if not exist_user:
            return JSONResponse(status_code=200, content={
                "message": "user does not exists.",
                "status_code": 0
            })

        if ChangeuserActive.active == "true":
            await profile_collection.update_one({"user_id": user_id}, {"$set": {"active": "true"}})
        else:
            await profile_collection.update_one({"user_id": user_id}, {"$set": {"active": "false"}})

        return JSONResponse(status_code=200, content={
                "message": "active feild updated successfully.",
                "status_code": 1
            })

    except HTTPException as http_exc:
        raise http_exc  # Pass FastAPI exceptions
    
    except Exception as e:
         return JSONResponse(status_code=200, content={
            "message": f"Internal server error. {e}",
            "status_code": 0
        })
    

# Register Routers
app.include_router(linkedin_router)
app.include_router(google_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)