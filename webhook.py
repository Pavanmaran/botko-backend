from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
import requests
from groq import Groq
import os
from database import get_conn
from datetime import datetime

router = APIRouter(tags=["webhook"])
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

def get_agent_by_slug(slug: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM agents WHERE slug=%s AND is_active=TRUE", (slug,))
    agent = cur.fetchone()
    cur.close()
    conn.close()
    return agent

def get_history(agent_id: int, phone: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, message FROM conversations 
        WHERE agent_id=%s AND phone=%s 
        ORDER BY ts DESC LIMIT 20
    """, (agent_id, phone))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"role": r["role"], "content": r["message"]} for r in reversed(rows)]

def save_message(agent_id: int, phone: str, role: str, message: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (agent_id, phone, role, message) VALUES (%s, %s, %s, %s)",
        (agent_id, phone, role, message)
    )
    conn.commit()
    cur.close()
    conn.close()

def ask_ai(system_prompt: str, history: list, user_message: str) -> str:
    history.append({"role": "user", "content": user_message})
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}] + history,
            max_tokens=200,
            temperature=0.85
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Sorry, I'm having a moment. Please try again!"

def send_whatsapp(to: str, message: str, wa_token: str, wa_phone_id: str):
    url = f"https://graph.facebook.com/v22.0/{wa_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {wa_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    res = requests.post(url, headers=headers, json=payload)
    print(f"WhatsApp status: {res.status_code}")

@router.get("/webhook/{slug}")
def verify(slug: str, request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    agent = get_agent_by_slug(slug)
    if not agent:
        return PlainTextResponse("Not found", status_code=404)
    if mode == "subscribe" and token == agent["verify_token"]:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)

@router.post("/webhook/{slug}")
async def webhook(slug: str, request: Request):
    data = await request.json()
    try:
        agent = get_agent_by_slug(slug)
        if not agent:
            return {"status": "agent not found"}
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return {"status": "no message"}
        msg = messages[0]
        from_number = msg["from"]
        if msg.get("type") != "text":
            send_whatsapp(from_number, "Please send text only!", agent["wa_token"], agent["wa_phone_id"])
            return {"status": "ok"}
        user_text = msg["text"]["body"]
        save_message(agent["id"], from_number, "user", user_text)
        history = get_history(agent["id"], from_number)
        reply = ask_ai(agent["system_prompt"], history, user_text)
        save_message(agent["id"], from_number, "assistant", reply)
        send_whatsapp(from_number, reply, agent["wa_token"], agent["wa_phone_id"])
    except Exception as e:
        print(f"Webhook error: {e}")
    return {"status": "ok"}