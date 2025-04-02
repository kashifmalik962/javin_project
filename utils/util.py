from twilio.rest import Client
import base64
import os
import traceback
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from jose import JWTError, jwt
import re
from fastapi import HTTPException
from jose import jwt, JWTError
from PyPDF2 import PdfReader, PdfWriter

# Load env
load_dotenv(find_dotenv(), verbose=True)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES", 43200))
ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES", 60))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set in the environment variables.")

print(SECRET_KEY, type(SECRET_KEY))
print(ALGORITHM, type(ALGORITHM))
print(STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES, type(STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES))

def send_watsapp_message(phone, otp_code):
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            body=f'{otp_code} is your verification code. Do not share it.',
            to=f'whatsapp:+91{phone}'
        )
        print(message.sid)
        return {"status": "ok", "message": "Successfully sent message via WhatsApp."}
    except Exception as e:
        print(f"WhatsApp sending failed: {e}")
        traceback.print_exc()
        return {"status": "fail", "message": "Failed to send WhatsApp message."}

def send_sms_message(phone, otp_code):
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_='+17257453071',
            body=f'{otp_code} is your verification code. Do not share it.',
            to=f'+91{phone}'
        )
        print(message.sid)
        return {"status": "ok", "message": "Successfully sent message via SMS."}
    except Exception as e:
        print(f"SMS sending failed: {e}")
        traceback.print_exc()
        return {"status": "fail", "message": "Failed to send SMS message."}

def encode_base64(password):
    base64_string = base64.b64encode(password.encode("ascii")).decode("ascii")
    print(f"Encoded string: {base64_string}")
    return base64_string

def decode_base64(encoded_password):
    decoded_string = base64.b64decode(encoded_password.encode("ascii")).decode("ascii")
    print(f"Decoded string: {decoded_string}")
    return decoded_string


# Generate JWT Token
def create_access_token(data: dict, type="student"):
    if type == "admin":
        # print(ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES, "ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES")
        access_token_expires = timedelta(minutes=ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        # print(STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES, "STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES")
        access_token_expires = timedelta(minutes=STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES)

    # print(f"Encoding JWT with algorithm: {ALGORITHM}")
    # print(f"Encoding JWT with STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES: {STUDENT_ACCESS_TOKEN_EXPIRE_MINUTES}")
    # print(f"Encoding JWT with SECRET_KEY: {SECRET_KEY}")
    to_encode = data.copy()

    expire = datetime.utcnow() + access_token_expires
    to_encode.update({"exp": expire})

    # print(f"Encoding JWT with algorithm: {ALGORITHM}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


# Verify / Validate - Token
def validate_token(token: str):
    """
    Validate the JWT token and return the decoded payload.
    """
    try:
        # Decode the token using the secret key and algorithm
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Optionally, check if token is expired
        if datetime.utcfromtimestamp(payload["exp"]) < datetime.utcnow():
            raise HTTPException(status_code=200, detail="Token has expired.")
        
        return payload
    except JWTError:
        raise HTTPException(status_code=200, detail="Invalid token.")

# Validate phone number
def validation_number(phone: str) -> str:
    phone_number = phone.strip()  # Remove spaces

    if not phone_number:
        raise HTTPException(status_code=200, detail="Phone number is required.")

    # Ensure the number is purely numeric after removing `+`
    if phone_number.startswith("+"):
        phone_number = phone_number[1:]

    if not phone_number.isdigit():
        raise HTTPException(status_code=200, detail="Phone number should contain only digits.")

    # Check if the phone number starts with '91' and has a total of 12 digits
    if phone_number.startswith("91") and len(phone_number) == 12:
        return phone_number[-10:]  # Extract last 10 digits

    # If it's already a 10-digit number, return it directly
    if len(phone_number) == 10:
        return phone_number

    raise HTTPException(status_code=200, detail="Invalid phone number format. Use a valid 10-digit number.")


# Validate Email
def is_valid_email(email):
    """
    Validate an email address using a regular expression.
    """
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    
    if re.match(email_pattern, email):
        print("math")
        return True
    
    print(" not mathc")
    # Instead of returning an exception, raise it
    raise HTTPException(status_code=200, detail="Invalid email format.")



def save_pdf_from_base64(base64_string: str, filename: str, upload_folder="static/resumes") -> str:
    try:
        print(upload_folder, "upload_folder")
        pdf_path = os.path.join(upload_folder, filename)
        
        # Decode Base64 and save initial PDF
        pdf_bytes = base64.b64decode(base64_string)
        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(pdf_bytes)
        
        # Compress the PDF
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        # Copy all pages with compression
        for page in reader.pages:
            page.compress_content_streams()  # Compress content streams
            writer.add_page(page)
        
        # Save compressed PDF (overwrites original)
        with open(pdf_path, "wb") as compressed_pdf:
            writer.write(compressed_pdf)
        
        return pdf_path
        
    except Exception as e:
        raise HTTPException(status_code=200, detail=f"Error while saving or compressing PDF: {str(e)}")
