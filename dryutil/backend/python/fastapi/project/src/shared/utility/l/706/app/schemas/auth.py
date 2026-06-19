from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone:     str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str
