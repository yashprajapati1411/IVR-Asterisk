"""
Authentication router for Trinay Orthopedic Hospital Receptionist Dashboard.
Credentials:
  Username: trinay@2026
  Password: 8998
"""
import hashlib
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["Auth"])

AUTH_USERNAME = "trinay@2026"
AUTH_PASSWORD = "8998"
# Cryptographically deterministic token for valid credentials
AUTH_TOKEN = hashlib.sha256(f"trinay_salt_{AUTH_USERNAME}_{AUTH_PASSWORD}".encode()).hexdigest()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest):
    if req.username.strip() == AUTH_USERNAME and req.password.strip() == AUTH_PASSWORD:
        return {
            "success": True,
            "token": AUTH_TOKEN,
            "username": AUTH_USERNAME,
            "role": "receptionist"
        }
    raise HTTPException(status_code=401, detail="યુઝરનેમ અથવા પાસવર્ડ ખોટો છે (Invalid username or password)")

@router.get("/verify")
def verify(x_auth_token: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    token = x_auth_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    
    if token == AUTH_TOKEN:
        return {"success": True, "valid": True, "username": AUTH_USERNAME}
    raise HTTPException(status_code=401, detail="Unauthorized")
