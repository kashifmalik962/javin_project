import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI()

FIREBASE_API_KEY = "AIzaSyA5Laf4qbawaFjIDDZePgtmMVtycJ7MuFw"  # Replace with your actual API key

class PhoneNumber(BaseModel):
    phone_number: str

class VerifyOTP(BaseModel):
    phone_number: str
    code: str
    session_info: str  # Session info ko bhi include karo

# Step 1: Send OTP via REST API
@app.post("/send-otp")
async def send_otp(phone: PhoneNumber):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={FIREBASE_API_KEY}"
    payload = {
        "phoneNumber": phone.phone_number,
        "recaptchaToken": "I am not a robot"  # Testing ke liye chhod sakte ho abhi
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        session_info = response.json().get("sessionInfo")
        return {"message": "OTP sent (check Firebase console if test number)", "session_info": session_info}
    raise HTTPException(status_code=400, detail=response.json())

# Step 2: Verify OTP via REST API
@app.post("/verify-otp")
async def verify_otp(data: VerifyOTP):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key={FIREBASE_API_KEY}"
    payload = {
        "sessionInfo": data.session_info,
        "code": data.code
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return {"message": "OTP verified", "id_token": response.json().get("idToken")}
    raise HTTPException(status_code=400, detail=response.json())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)