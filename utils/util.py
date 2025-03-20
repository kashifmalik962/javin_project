from twilio.rest import Client
import base64
import os
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from jose import JWTError, jwt

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(find_dotenv(), verbose=True)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# Send Watsapp message
def send_watsapp_message(phone,otp_code):
    try:
        client = Client(account_sid, auth_token)

        message = client.messages.create(
            from_='whatsapp:+14155238886',  # Twilio Sandbox number
            body=f'{otp_code} is your verification code. For your security, do not share this code.',
            to=f'whatsapp:+91{phone}'  # Verify number in sandbox
        )
        
        print(message.sid)
        return {"status": "ok", "message": "Sucessfully message sent on watsapp."}
    except:
        return {"status": "fail", "message": "Failed to sent message on watsapp."}


# Send SMS Message
def send_sms_message(phone,otp_code):
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_='+15124123378',
            body=f'{otp_code} is your verification code. For your security, do not share this code.',
            to=f'+91{phone}'
        )
        print(message.sid)
        return {"status": "ok", "message": "Sucessfully message sent on sms."}
    except:
        return {"status": "fail", "message": "Failed to sent message on sms."}


# Encode password
def encode_base64(password):
    sample_string = password
    sample_string_bytes = sample_string.encode("ascii")

    base64_bytes = base64.b64encode(sample_string_bytes)
    base64_string = base64_bytes.decode("ascii")

    print(f"Encoded string: {base64_string}")
    return base64_string

# Decode password
def dencode_base64(password):
    base64_string = password
    base64_bytes = base64_string.encode("ascii")

    sample_string_bytes = base64.b64decode(base64_bytes)
    sample_string = sample_string_bytes.decode("ascii")
    print(f"Decoded string: {sample_string}")
    return sample_string


# Generate JWT Token
def create_access_token(data: dict):
    print(ACCESS_TOKEN_EXPIRE_MINUTES, type(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = data.copy()

    if access_token_expires:
        expire = datetime.utcnow() + access_token_expires
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt