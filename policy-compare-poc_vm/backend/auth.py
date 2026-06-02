# backend/auth.py 
from jose import jwt, JWTError 
from passlib.context import CryptContext 
from datetime import datetime, timedelta 
from typing import Optional 
import os 
 
SECRET_KEY = os.getenv("SECRET_KEY", "demo-secret-key-change-me") 
ALGORITHM = "HS256" 
ACCESS_TOKEN_EXPIRE_MINUTES = 60 
 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") 
 
# Demo in-memory user store. Replace with real user DB / IAM in prod. 
USERS = { 
    "alice": {"username":"alice","hashed_password":pwd_context.hash("alicepass"), "roles":["admin"]}, 
    "bob": {"username":"bob","hashed_password":pwd_context.hash("bobpass"), "roles":["auditor"]}, 
    "carol": {"username":"carol","hashed_password":pwd_context.hash("carolpass"), "roles":["viewer"]}, 
} 
 
def authenticate_user(username: str, password: str): 
    user = USERS.get(username) 
    if not user: 
        return None 
    if not pwd_context.verify(password, user["hashed_password"]): 
        return None 
    return {"username": user["username"], "roles": user["roles"]} 
 
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None): 
    to_encode = data.copy() 
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)) 
    to_encode.update({"exp": expire}) 
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) 
 
def decode_token(token: str): 
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) 
        return payload 
    except JWTError: 
        return None 
 
def require_role(token_payload: dict, allowed_roles: list): 
    if not token_payload: 
        return False 
    roles = token_payload.get("roles", []) 
    return any(r in roles for r in allowed_roles) 