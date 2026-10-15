"""
Authentication router for Trinay Orthopedic Hospital Receptionist Dashboard.
Credentials:
  Username: trinay@2026
  Password: 8998
"""
import time
import hashlib
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, Dict, List

router = APIRouter(prefix="/api/auth", tags=["Auth"])

AUTH_USERNAME = "trinay@2026"
AUTH_PASSWORD = "8998"
# Cryptographically deterministic token for valid credentials
AUTH_TOKEN = hashlib.sha256(f"trinay_salt_{AUTH_USERNAME}_{AUTH_PASSWORD}".encode()).hexdigest()

# In-memory brute-force protection: IP -> list of failed attempt timestamps
_failed_attempts: Dict[str, List[float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SEC = 900 # 15 minutes lockout

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old attempts and check if locked out
    attempts = [t for t in _failed_attempts.get(client_ip, []) if now - t < LOCKOUT_DURATION_SEC]
    _failed_attempts[client_ip] = attempts

    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        remaining = int((LOCKOUT_DURATION_SEC - (now - attempts[0])) / 60) + 1
        raise HTTPException(
            status_code=429, 
            detail=f"ઘણા ખોટા પ્રયાસો થયા છે. કૃપા કરીને {remaining} મિનિટ પછી ફરી પ્રયાસ કરો. (Too many failed attempts. Locked out for {remaining} minutes.)"
        )

    if req.username.strip() == AUTH_USERNAME and req.password.strip() == AUTH_PASSWORD:
        _failed_attempts.pop(client_ip, None)
        return {
            "success": True,
            "token": AUTH_TOKEN,
            "username": AUTH_USERNAME,
            "role": "receptionist"
        }

    # Record failed attempt
    _failed_attempts.setdefault(client_ip, []).append(now)
    attempts_left = MAX_FAILED_ATTEMPTS - len(_failed_attempts[client_ip])
    if attempts_left > 0:
        msg = f"યુઝરનેમ અથવા પાસવર્ડ ખોટો છે ({attempts_left} પ્રયાસ બાકી)"
    else:
        msg = f"ઘણા ખોટા પ્રયાસો. ૧૫ મિનિટ માટે લોક કરવામાં આવ્યું છે."
    raise HTTPException(status_code=401, detail=msg)


@router.get("/verify")
def verify(x_auth_token: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    token = x_auth_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    
    if token == AUTH_TOKEN:
        return {"success": True, "valid": True, "username": AUTH_USERNAME}
    raise HTTPException(status_code=401, detail="Unauthorized")
