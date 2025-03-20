from pydantic import BaseModel, EmailStr
from typing import Optional


# Profile Model
class Profile(BaseModel):
    full_name: str
    email: EmailStr
    email2: EmailStr
    phone: str
    phone2: str
    country: str
    address: Optional[str] = None
    resume_name: Optional[str] = None
    linkedin: Optional[str] = None
    current_city: Optional[str] = None
    preferred_city: Optional[str] = None
    summary_of_profile: Optional[str] = None
    college_background: Optional[str] = None
    current_organization: Optional[str] = None
    total_work_experience_years: Optional[int] = None
    comment: Optional[str] = None
    referred_by: Optional[str] = None
    current_ctc: Optional[float] = None
    desired_ctc: Optional[float] = None
    github: Optional[str] = None
    leetcode: Optional[str] = None
    codechef: Optional[str] = None



class Admin(BaseModel):
    email: str
    password: str


class Send_Otp_Number(BaseModel):
    phone: str

class Veryfy_OTP(BaseModel):
    phone: str
    otp: str

class DownloadResume(BaseModel):
    email: str

