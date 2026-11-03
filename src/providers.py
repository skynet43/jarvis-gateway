"""Explicit, transient model-provider connections. Keys stay in process memory."""
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from control import auth

router=APIRouter(prefix="/control/providers",dependencies=[Depends(auth)],tags=["Providers"])
CATALOG={
 "ollama":("Ollama","local","http://127.0.0.1:11434"),
 "lm-studio":("LM Studio","openai","http://127.0.0.1:1234/v1"),
 "llama-cpp":("llama.cpp","openai","http://127.0.0.1:8080/v1"),
 "vllm":("vLLM","openai","http://127.0.0.1:8000/v1"),
 "openai":("OpenAI","openai","https://api.openai.com/v1"),
 "anthropic":("Anthropic","anthropic","https://api.anthropic.com/v1"),
 "gemini":("Gemini","gemini","https://generativelanguage.googleapis.com/v1beta"),
 "openrouter":("OpenRouter","openai","https://openrouter.ai/api/v1"),
 "groq":("Groq","openai","https://api.groq.com/openai/v1"),
 "mistral":("Mistral","openai","https://api.mistral.ai/v1"),
 "xai":("xAI","openai","https://api.x.ai/v1"),
 "custom-local":("Other local OpenAI API","openai",None),
}
CONNECTIONS={}
class Connection(BaseModel):
    provider:str
    endpoint:str|None=None
    api_key:str=Field(default="",max_length=4096)

class ChatRequest(BaseModel):
    model:str=Field(min_length=1,max_length=200)
    prompt:str=Field(min_length=1,max_length=8000)

def endpoint_for(req:Connection):
    if req.provider not in CATALOG:
        raise HTTPException(400,"Unknown provider")
    default=CATALOG[req.provider][2]
    url=(req.endpoint or default or "").rstrip("/")
    parsed=urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.endswith("//"):
        raise HTTPException(400,"Invalid endpoint")
    if req.provider in ("ollama","lm-studio","llama-cpp","vllm","custom-local"):
        if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1"):
            raise HTTPException(400,"Local providers must use loopback HTTP")
        if not parsed.port or not 1<=parsed.port<=65535:
            raise HTTPException(400,"Local provider port required")
    elif url!=default:
        raise HTTPException(400,"Hosted provider endpoint is fixed")
    return url

@router.get("")
def catalog():
    return [{"id":key,"name":row[0],"protocol":row[1],"default_endpoint":row[2],"connected":key in CONNECTIONS} for key,row in CATALOG.items()]

@router.post("/connect")
async def connect_provider(req:Connection):
    url=endpoint_for(req)
    protocol=CATALOG[req.provider][1]
    if req.provider not in ("ollama","lm-studio","llama-cpp","vllm","custom-local") and not req.api_key:
        raise HTTPException(400,"API key required")
    path="/api/tags" if protocol=="local" else "/models"
    headers={"Authorization":"Bearer "+req.api_key} if req.api_key else {}
    if protocol=="anthropic":
        headers={"x-api-key":req.api_key,"anthropic-version":"2023-06-01"}
    if protocol=="gemini":
        headers={"x-goog-api-key":req.api_key}
    try:
        async with httpx.AsyncClient(timeout=8,trust_env=False,follow_redirects=False) as client:
            response=await client.get(url+path,headers=headers)
            response.raise_for_status()
            data=response.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,"Provider connection failed ("+type(exc).__name__+")") from None
    models=data.get("models",[]) if protocol in ("local","gemini") else data.get("data",[])
    names=[m.get("name") or m.get("id") for m in models if isinstance(m,dict)]
    CONNECTIONS[req.provider]={"endpoint":url,"api_key":req.api_key,"models":names}
    return {"provider":req.provider,"connected":True,"models":names[:100]}

@router.post("/{provider}/disconnect")
def disconnect_provider(provider:str):
    CONNECTIONS.pop(provider,None)
    return {"provider":provider,"connected":False}

@router.post("/{provider}/chat")
async def provider_chat(provider:str,req:ChatRequest):
    connection=CONNECTIONS.get(provider)
    if not connection:raise HTTPException(409,"Provider is not connected")
    if req.model not in connection["models"]:raise HTTPException(400,"Choose a model returned by this provider")
    url=connection["endpoint"]
    key=connection["api_key"]
    protocol=CATALOG[provider][1]
    if protocol=="local":
        path="/api/chat"
        headers={}
        payload={"model":req.model,"messages":[{"role":"user","content":req.prompt}],"stream":False,"options":{"num_predict":2048}}
    elif protocol=="anthropic":
        path="/messages"
        headers={"x-api-key":key,"anthropic-version":"2023-06-01"}
        payload={"model":req.model,"max_tokens":2048,"messages":[{"role":"user","content":req.prompt}]}
    elif protocol=="gemini":
        path="/"+req.model+":generateContent"
        headers={"x-goog-api-key":key}
        payload={"contents":[{"parts":[{"text":req.prompt}]}]}
    else:
        path="/chat/completions"
        headers={"Authorization":"Bearer "+key} if key else {}
        payload={"model":req.model,"messages":[{"role":"user","content":req.prompt}],"max_tokens":2048}
    try:
        async with httpx.AsyncClient(timeout=120,trust_env=False,follow_redirects=False) as client:
            async with client.stream("POST",url+path,headers=headers,json=payload) as response:
                response.raise_for_status()
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>262144:raise HTTPException(502,"Provider response too large")
        body=__import__("json").loads(data)
        if protocol=="local":text=body["message"]["content"]
        elif protocol=="anthropic":text="\n".join(x.get("text","") for x in body["content"] if x.get("type")=="text")
        elif protocol=="gemini":text="\n".join(x.get("text","") for x in body["candidates"][0]["content"]["parts"])
        else:text=body["choices"][0]["message"]["content"]
        return {"provider":provider,"model":req.model,"text":text[:262144]}
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError):
        raise HTTPException(502,"Provider inference failed") from None
