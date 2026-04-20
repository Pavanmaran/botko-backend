from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from database import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])
SECRET = os.environ.get("SECRET_KEY", "botko_secret_123")

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

def create_token(tenant_id: int, email: str):
    payload = {
        "tenant_id": tenant_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

@router.post("/register")
def register(req: RegisterRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO tenants (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (req.name, req.email, hashed)
        )
        tenant_id = cur.fetchone()["id"]
        conn.commit()
        token = create_token(tenant_id, req.email)
        return {"token": token, "tenant_id": tenant_id}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Email already exists")
    finally:
        cur.close()
        conn.close()

@router.post("/login")
def login(req: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tenants WHERE email=%s", (req.email,))
    tenant = cur.fetchone()
    cur.close()
    conn.close()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(req.password.encode(), tenant["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(tenant["id"], tenant["email"])
    return {"token": token, "tenant_id": tenant["id"], "name": tenant["name"]}