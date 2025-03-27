import random
import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth

# Replace with your service account key path
cred = credentials.Certificate("./wtt-1b53c-firebase-adminsdk-fbsvc-2a243a9d76.json")
firebase_admin.initialize_app(cred)

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(phone_number, otp):
    # Implement your SMS sending logic here (e.g., using Twilio)
    # For example:
    # client = twilio.rest.Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     to=phone_number,
    #     from_="+YOUR_TWILIO_PHONE_NUMBER",
    #     body=f"Your OTP is: {otp}"
    # )
    print(f"Sending OTP {otp} to {phone_number}") # Replace with your actual SMS sending logic
    return True

def verify_otp(phone_number, entered_otp):
    # Retrieve the stored OTP from your database
    # Compare the entered OTP with the stored OTP
    # Return True if they match, False otherwise
    print(f"Verifying OTP {entered_otp} for {phone_number}")
    # Replace with your database lookup and comparison logic
    return True # Replace with your database lookup and comparison logic

def create_user(phone_number):
    # Create a user in Firebase Authentication
    # Use the Firebase Admin SDK to create a user
    try:
        user = auth.create_user(phone_number=phone_number)
        print(f"User created successfully with UID: {user.uid}")
        return user
    except Exception as e:
        print(f"Error creating user: {e}")
        return None