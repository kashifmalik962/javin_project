from twilio.rest import Client
import base64
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")


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


def encode_base64(password):
    sample_string = password
    sample_string_bytes = sample_string.encode("ascii")

    base64_bytes = base64.b64encode(sample_string_bytes)
    base64_string = base64_bytes.decode("ascii")

    print(f"Encoded string: {base64_string}")
    return base64_string


def dencode_base64(password):
    base64_string = password
    base64_bytes = base64_string.encode("ascii")

    sample_string_bytes = base64.b64decode(base64_bytes)
    sample_string = sample_string_bytes.decode("ascii")
    print(f"Decoded string: {sample_string}")
    return sample_string


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
