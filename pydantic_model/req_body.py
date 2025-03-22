from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union


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
    sub_student_id: List[int] = None


class RegisterStudent(BaseModel):
    email: str
    phone: str


class RegisterSubStudent(BaseModel):
    email: str
    phone: str
    parent_id: int


class LoginStudent(BaseModel):
    email: str
    phone: str

class Admin(BaseModel):
    email: str
    password: str


class Send_Otp_Number(BaseModel):
    phone: str

class Veryfy_OTP(BaseModel):
    phone: str
    otp: str

class DownloadResume(BaseModel):
    student_id: int


                            # ACTIVITY PATH MODULE

class ActivityPathModule(BaseModel):
    activity_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[Union[List[str], str]] = None
    correct_answer: Optional[str] = None
    mark: Optional[int] = None