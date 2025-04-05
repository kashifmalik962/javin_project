from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union
from enum import Enum

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
    sub_user_id: Optional[List[int]] = []


# Profile choice
class RegisterUserType(str, Enum):
    primary = "primary"
    secondary = "secondary"


class RegisterUser(BaseModel):
    email: EmailStr
    phone: str


class RegisterSubUser(BaseModel):
    email: EmailStr
    phone: str
    parent_id: int


class LoginUser(BaseModel):
    email: EmailStr
    phone: str

class Admin(BaseModel):
    email: EmailStr
    password: str


# OTP Choice
class OTP_Type(str, Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    email = "email"

class Send_Otp(BaseModel):
    notifier: str
    type: OTP_Type


class Veryfy_OTP(BaseModel):
    notifier: str
    otp: str

class DownloadResume(BaseModel):
    user_id: int

# class UpdateResume(BaseModel):
#     resume_name: Optional[str] = None


                            # ACTIVITY PATH MODULE

# Define an Enum for dropdown options
class QuestionType(str, Enum):
    mcq = "mcq"
    text = "text"
    video = "video"


class ActivityPathModule(BaseModel):
    activity_name: Optional[str] = None
    description: Optional[str] = None
    question_type: QuestionType
    question: Optional[str] = None
    options: Optional[Union[List[str], str]] = None
    correct_answer: Optional[str] = None
    mark: Optional[int] = None



                         # ADMIN


class ActiveOption(str, Enum):
    true = "true"
    false = "false"

class ChangeUserActive(BaseModel):
    active: ActiveOption