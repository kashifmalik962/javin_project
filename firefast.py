from fastapi import FastAPI
import requests

app = FastAPI()

FIREBASE_API_KEY = "AIzaSyA5Laf4qbawaFjIDDZePgtmMVtycJ7MuFw"  # Firebase se API Key lein

# 📌 ✅ STEP 1: OTP Send Karna
@app.post("/send-otp/")
def send_otp(phone: str):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={FIREBASE_API_KEY}"
    
    payload = {
        "phoneNumber": phone,
        "recaptchaToken": "fake-recaptcha-token"  # Firebase ke liye fake token use karein
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    
    return response.json()  # Firebase ka response return karein


# 📌 ✅ STEP 2: OTP Verify Karna
@app.post("/verify-otp/")
def verify_otp(session_info: str, code: str):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key={FIREBASE_API_KEY}"

    payload = {
        "sessionInfo": session_info,  # Firebase se mila sessionInfo
        "code": code  # User ka enter kiya OTP
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    
    return response.json()  # Firebase ka response return karein



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("firefast:app", host="127.0.0.1", port=8000, reload=True)
