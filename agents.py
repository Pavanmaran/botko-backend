from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import jwt
import os
from database import get_conn

router = APIRouter(prefix="/agents", tags=["agents"])
SECRET = os.environ.get("SECRET_KEY", "botko_secret_123")

def get_tenant(token: str):
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload["tenant_id"]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

class AgentCreate(BaseModel):
    name: str
    system_prompt: str
    wa_token: Optional[str] = ""
    wa_phone_id: Optional[str] = ""
    verify_token: Optional[str] = "botko123"

@router.post("/create")
def create_agent(req: AgentCreate, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    tenant_id = get_tenant(token)
    slug = req.name.lower().replace(" ", "_") + "_" + str(tenant_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO agents (tenant_id, name, slug, system_prompt, wa_token, wa_phone_id, verify_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, slug
        """, (tenant_id, req.name, slug, req.system_prompt, req.wa_token, req.wa_phone_id, req.verify_token))
        agent = cur.fetchone()
        conn.commit()
        return {
            "agent_id": agent["id"],
            "slug": agent["slug"],
            "webhook_url": f"https://botko.onrender.com/webhook/{agent['slug']}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.get("/list")
def list_agents(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    tenant_id = get_tenant(token)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, slug, is_active, created_at FROM agents WHERE tenant_id=%s", (tenant_id,))
    agents = cur.fetchall()
    cur.close()
    conn.close()
    return {"agents": agents}