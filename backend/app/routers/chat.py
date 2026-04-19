"""
/api/chat  —  AI proxy endpoint with support for both Gemini and OpenAI
"""
from __future__ import annotations

import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/chat", tags=["chat"])

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL   = "gpt-4o-mini"
GEMINI_MODEL   = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "You are EpiChat AI. Explain EEG results and epilepsy precautions. "
    "You are not a doctor. Always include disclaimer."
)

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    reply: str

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    # 1) Try Google Gemini API First (Free tier friendly)
    if gemini_key:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={gemini_key}"
        
        contents = []
        for m in req.history:
            role = "model" if m.get("role") == "assistant" else "user"
            text = m.get("text", m.get("content", ""))
            contents.append({"role": role, "parts": [{"text": text}]})
            
        contents.append({"role": "user", "parts": [{"text": req.message}]})
        
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(gemini_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
                return ChatResponse(reply=reply)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return ChatResponse(reply="🤖 [Mock Mode] Google Gemini rate limit exceeded. Please try again later.")
            if e.response.status_code == 400:
                return ChatResponse(reply="🤖 [Mock Mode] Invalid request to Gemini API. Please check your API key and setup.")
            body = e.response.json() if e.response.content else {}
            msg  = body.get("error", {}).get("message", str(e))
            raise HTTPException(status_code=e.response.status_code, detail=f"Gemini error: {msg}")
        except httpx.RequestError as e:
            return ChatResponse(reply=f"🤖 [Mock Mode] Network error reaching Gemini: {e}")

    # 2) Fallback to OpenAI API
    if not openai_key:
        return ChatResponse(reply="🤖 [Mock Mode] Please add an OPENAI_API_KEY to the .env file for OpenAI fallback.")

    # Build messages with system prompt prepended for OpenAI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Append history
    for m in req.history:
        messages.append({
            "role": "assistant" if m.get("role") == "assistant" else "user",
            "content": m.get("text", m.get("content", ""))
        })
        
    # Append latest message
    messages.append({"role": "user", "content": req.message})

    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7,
    }

    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OPENAI_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return ChatResponse(reply=reply)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return ChatResponse(reply="🤖 [Mock Mode] OpenAI API rate limit exceeded (Quota exhausted). Please check your OpenAI billing details or try again later.")
        if e.response.status_code == 401:
            return ChatResponse(reply="🤖 [Mock Mode] Invalid OpenAI API key. Please check the key in your .env file.")
        body = e.response.json() if e.response.content else {}
        msg  = body.get("error", {}).get("message", str(e))
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenAI error: {msg}")
    except httpx.RequestError as e:
        return ChatResponse(reply=f"🤖 [Mock Mode] Network error reaching OpenAI: {e}")
