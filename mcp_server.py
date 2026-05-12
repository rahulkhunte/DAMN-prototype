# mcp_server.py — DAMN v2.1 — fixed all issues
import os, time, json, requests
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="DAMN - Decentralized AI Memory Network")
PINATA_JWT = os.getenv("PINATA_JWT")
PROXY_SECRET = os.getenv("AGENTICMARKET_SECRET", "")
HEADERS = {"Authorization": f"Bearer {PINATA_JWT}"}

# ── FIX #1: Persist memory_index to disk ──────────────────────
INDEX_FILE = "/home/ubuntu/DAMN-prototype/memory_index.json"

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {}

def save_index(index):
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f)

memory_index = load_index()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def verify_proxy(request: Request, call_next):
    open_paths = ["/health", "/", "/mcp", "/docs", "/openapi.json", "/tools"]
    if any(request.url.path.startswith(p) for p in open_paths):
        return await call_next(request)
    if PROXY_SECRET and request.headers.get("X-AgenticMarket-Secret") != PROXY_SECRET:
        client_host = request.client.host if request.client else "unknown"
        if client_host not in ("127.0.0.1", "localhost"):
            return Response("Unauthorized", status_code=401)
    return await call_next(request)

# ── IPFS helpers ───────────────────────────────────────────────
def pin_to_ipfs(data: dict) -> str:
    res = requests.post(
        "https://api.pinata.cloud/pinning/pinJSONToIPFS",
        json={"pinataContent": data,
              "pinataMetadata": {"name": f"DAMN-{int(time.time())}"}},
        headers=HEADERS, timeout=15)
    res.raise_for_status()
    return res.json()["IpfsHash"]

def fetch_from_ipfs(cid: str) -> dict:
    res = requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}", timeout=15)
    res.raise_for_status()
    return res.json()

# ── FIX #2: Pydantic models for Swagger ───────────────────────
class StoreMemoryRequest(BaseModel):
    content: str
    tags: Optional[List[str]] = []

class RetrieveMemoryRequest(BaseModel):
    memory_id: str

class SearchMemoryRequest(BaseModel):
    query: str

# ── MCP Tools definition ───────────────────────────────────────
MCP_TOOLS = [
    {"name": "store_memory",
     "description": "Store a memory permanently on IPFS via Pinata. Returns memory_id and IPFS CID.",
     "inputSchema": {"type": "object",
         "properties": {
             "content": {"type": "string"},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["content"]}},
    {"name": "retrieve_memory",
     "description": "Retrieve a memory from IPFS by its memory_id.",
     "inputSchema": {"type": "object",
         "properties": {"memory_id": {"type": "string"}},
         "required": ["memory_id"]}},
    {"name": "list_memories",
     "description": "List all stored memory IDs, tags, and IPFS CIDs.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "search_memories",
     "description": "Search stored memories by tag keyword.",
     "inputSchema": {"type": "object",
         "properties": {"query": {"type": "string"}},
         "required": ["query"]}}
]

# ── MCP JSON-RPC handler ───────────────────────────────────────
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id", 1)

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"protocolVersion": "2024-11-05",
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "DAMN Memory", "version": "2.1"}}}

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}

    elif method == "tools/call":
        params = body.get("params", {})
        tool = params.get("name", "")
        args = params.get("arguments", {})
        try:
            result = await handle_tool(tool, args)
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": str(result)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": str(e)}}

    elif method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}

# ── Shared tool logic ──────────────────────────────────────────
async def handle_tool(tool: str, args: dict):
    global memory_index
    if tool == "store_memory":
        content = args.get("content", "")
        tags = args.get("tags", [])
        data = {"content": content, "tags": tags,
                "timestamp": int(time.time()), "version": "DAMN-v2"}
        cid = pin_to_ipfs(data)
        memory_id = f"mem_{int(time.time())}"
        memory_index[memory_id] = {"cid": cid, "tags": tags, "timestamp": data["timestamp"]}
        save_index(memory_index)  # FIX #1: persist
        return {"memory_id": memory_id, "ipfs_cid": cid,
                "gateway_url": f"https://gateway.pinata.cloud/ipfs/{cid}", "permanent": True}

    elif tool == "retrieve_memory":
        mid = args.get("memory_id", "")
        if mid not in memory_index:
            return {"error": f"Memory {mid} not found"}
        cid = memory_index[mid]["cid"]
        return {"memory_id": mid, "ipfs_cid": cid, "data": fetch_from_ipfs(cid)}

    elif tool == "list_memories":
        return {"total": len(memory_index),
                "memories": [{"memory_id": k, "tags": v["tags"],
                               "timestamp": v["timestamp"], "cid": v["cid"]}
                              for k, v in memory_index.items()]}

    elif tool == "search_memories":
        query = args.get("query", "").lower()
        results = [{"memory_id": mid, "tags": meta["tags"], "cid": meta["cid"]}
                   for mid, meta in memory_index.items()
                   if any(query in tag.lower() for tag in meta["tags"])]
        return {"results": results, "count": len(results)}

    raise ValueError(f"Unknown tool: {tool}")

# ── REST endpoints (FIX #2: Pydantic + FIX #4: all 4 tools) ───
@app.get("/")
def root():
    return {"name": "DAMN Memory", "version": "2.1",
            "mcp_endpoint": "/mcp", "health": "/health"}

@app.get("/health")
def health():
    try:
        r = requests.get("https://api.pinata.cloud/data/testAuthentication",
                         headers=HEADERS, timeout=5)
        pinata_ok = r.status_code == 200
    except:
        pinata_ok = False

    # Check pin count
    try:
        pins = requests.get("https://api.pinata.cloud/data/pinList?status=pinned&pageLimit=1",
                            headers=HEADERS, timeout=5)
        pin_count = pins.json().get("count", 0)
    except:
        pin_count = -1

    return {"status": "running", "memories_cached": len(memory_index),
            "storage": "IPFS via Pinata", "pinata_connected": pinata_ok,
            "pinata_pins_used": pin_count, "pinata_pins_limit": 500,
            "chain": "coming_soon"}

@app.get("/tools")
def list_tools():
    return {"tools": [{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS]}

@app.post("/tools/store_memory")
async def store_memory_rest(req: StoreMemoryRequest):  # FIX #2
    return await handle_tool("store_memory", {"content": req.content, "tags": req.tags})

@app.post("/tools/retrieve_memory")  # FIX #4
async def retrieve_memory_rest(req: RetrieveMemoryRequest):
    return await handle_tool("retrieve_memory", {"memory_id": req.memory_id})

@app.get("/tools/list_memories")  # FIX #4
async def list_memories_rest():
    return await handle_tool("list_memories", {})

@app.post("/tools/search_memories")  # FIX #4
async def search_memories_rest(req: SearchMemoryRequest):
    return await handle_tool("search_memories", {"query": req.query})
