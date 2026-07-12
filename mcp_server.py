# mcp_server.py — DAMN v2.2
# Hybrid pinning: local Kubo node (primary) + Pinata (backup replication)
import os
import time
import json
import uuid
import tempfile
import threading

import requests
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="DAMN - Decentralized AI Memory Network", version="2.2")

PINATA_JWT = os.getenv("PINATA_JWT", "")
PROXY_SECRET = os.getenv("AGENTICMARKET_SECRET", "")
LOCAL_IPFS_API = os.getenv("LOCAL_IPFS_API", "http://127.0.0.1:5001")
LOCAL_IPFS_GATEWAY = os.getenv("LOCAL_IPFS_GATEWAY", "http://127.0.0.1:8080")
PINATA_HEADERS = {"Authorization": f"Bearer {PINATA_JWT}"} if PINATA_JWT else {}

# ── Persistent memory index ────────────────────────────────────
INDEX_FILE = os.getenv(
    "INDEX_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_index.json")
)
_index_lock = threading.Lock()


def load_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # keep the corrupt file for forensics instead of clobbering it
            os.replace(INDEX_FILE, INDEX_FILE + ".corrupt")
    return {}


def save_index(index):
    # atomic write: temp file in same dir, then rename
    dir_ = os.path.dirname(INDEX_FILE)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(index, f)
        os.replace(tmp, INDEX_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


memory_index = load_index()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Paths that never require the proxy secret. /mcp is exempt here so the MCP
# handshake (initialize, tools/list) stays open — tools/call is authed inside
# the endpoint. Everything else requires X-AgenticMarket-Secret unless the
# caller is localhost.
OPEN_EXACT = {"/", "/health", "/tools", "/openapi.json", "/mcp"}
OPEN_PREFIX = ("/docs", "/redoc")


def authorized(request: Request) -> bool:
    if not PROXY_SECRET:
        return True
    if request.headers.get("X-AgenticMarket-Secret") == PROXY_SECRET:
        return True
    client_host = request.client.host if request.client else "unknown"
    return client_host in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def verify_proxy(request: Request, call_next):
    path = request.url.path
    if path in OPEN_EXACT or path.startswith(OPEN_PREFIX):
        return await call_next(request)
    if not authorized(request):
        return Response("Unauthorized", status_code=401)
    return await call_next(request)


# ── IPFS helpers ───────────────────────────────────────────────
def pin_to_local_node(data: dict) -> Optional[str]:
    """Pin JSON to the local Kubo node. Returns CID or None if node is down."""
    try:
        payload = json.dumps(data).encode()
        res = requests.post(
            f"{LOCAL_IPFS_API}/api/v0/add?pin=true&cid-version=1",
            files={"file": ("memory.json", payload, "application/json")},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()["Hash"]
    except (requests.RequestException, KeyError, ValueError):
        return None


def pin_to_pinata(data: dict) -> Optional[str]:
    """Replicate JSON to Pinata. Returns CID or None on failure."""
    if not PINATA_JWT:
        return None
    try:
        res = requests.post(
            "https://api.pinata.cloud/pinning/pinJSONToIPFS",
            json={
                "pinataContent": data,
                "pinataMetadata": {"name": f"DAMN-{int(time.time())}"},
                "pinataOptions": {"cidVersion": 1},
            },
            headers=PINATA_HEADERS,
            timeout=15,
        )
        res.raise_for_status()
        return res.json()["IpfsHash"]
    except (requests.RequestException, KeyError, ValueError):
        return None


def pin_to_ipfs(data: dict) -> dict:
    """Pin to local node first, replicate to Pinata. At least one must succeed."""
    local_cid = pin_to_local_node(data)
    pinata_cid = pin_to_pinata(data)
    cid = local_cid or pinata_cid
    if cid is None:
        raise RuntimeError("Both local IPFS node and Pinata pinning failed")
    return {"cid": cid, "local": local_cid is not None, "pinata": pinata_cid is not None}


def fetch_from_ipfs(cid: str) -> dict:
    """Fetch from local gateway first (fast, free), then public gateways."""
    gateways = [
        f"{LOCAL_IPFS_GATEWAY}/ipfs/{cid}",
        f"https://gateway.pinata.cloud/ipfs/{cid}",
        f"https://ipfs.io/ipfs/{cid}",
    ]
    last_error = None
    for url in gateways:
        try:
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            return res.json()
        except (requests.RequestException, ValueError) as e:
            last_error = e
    raise RuntimeError(f"Could not fetch {cid} from any gateway: {last_error}")


# ── Pydantic models ────────────────────────────────────────────
class StoreMemoryRequest(BaseModel):
    content: str
    tags: Optional[List[str]] = []


class RetrieveMemoryRequest(BaseModel):
    memory_id: str


class SearchMemoryRequest(BaseModel):
    query: str


# ── MCP Tools definition ───────────────────────────────────────
MCP_TOOLS = [
    {
        "name": "store_memory",
        "description": "Store a memory permanently on IPFS (local node + Pinata backup). Returns memory_id and IPFS CID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content"],
        },
    },
    {
        "name": "retrieve_memory",
        "description": "Retrieve a memory from IPFS by its memory_id.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "list_memories",
        "description": "List all stored memory IDs, tags, and IPFS CIDs.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_memories",
        "description": "Search stored memories by tag or content keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]

# ── MCP JSON-RPC handler ───────────────────────────────────────
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id")

    # Notifications carry no id and must not receive a JSON-RPC response
    if method.startswith("notifications/"):
        return Response(status_code=202)

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "DAMN Memory", "version": "2.2"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}

    if method == "tools/call":
        if not authorized(request):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32001, "message": "Unauthorized"},
            }
        params = body.get("params", {})
        tool = params.get("name", "")
        args = params.get("arguments", {})
        try:
            result = await run_in_threadpool(handle_tool, tool, args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }
        except ValueError as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)},
            }
        except Exception as e:
            # tool execution failures are reported in-band per MCP spec
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool error: {e}"}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# ── Shared tool logic (sync — always called via threadpool) ───
def handle_tool(tool: str, args: dict):
    if tool == "store_memory":
        content = args.get("content", "")
        tags = args.get("tags") or []
        data = {
            "content": content,
            "tags": tags,
            "timestamp": int(time.time()),
            "version": "DAMN-v2",
        }
        pin = pin_to_ipfs(data)
        memory_id = f"mem_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        with _index_lock:
            memory_index[memory_id] = {
                "cid": pin["cid"],
                "tags": tags,
                "timestamp": data["timestamp"],
                "preview": content[:200],
                "pinned_local": pin["local"],
                "pinned_pinata": pin["pinata"],
            }
            save_index(memory_index)
        return {
            "memory_id": memory_id,
            "ipfs_cid": pin["cid"],
            "pinned_local": pin["local"],
            "pinned_pinata": pin["pinata"],
            "gateway_url": f"https://gateway.pinata.cloud/ipfs/{pin['cid']}",
            "permanent": True,
        }

    if tool == "retrieve_memory":
        mid = args.get("memory_id", "")
        with _index_lock:
            meta = memory_index.get(mid)
        if meta is None:
            return {"error": f"Memory {mid} not found"}
        return {"memory_id": mid, "ipfs_cid": meta["cid"], "data": fetch_from_ipfs(meta["cid"])}

    if tool == "list_memories":
        with _index_lock:
            items = [
                {"memory_id": k, "tags": v["tags"], "timestamp": v["timestamp"], "cid": v["cid"]}
                for k, v in memory_index.items()
            ]
        return {"total": len(items), "memories": items}

    if tool == "search_memories":
        query = args.get("query", "").lower()
        if not query:
            return {"results": [], "count": 0}
        with _index_lock:
            results = [
                {"memory_id": mid, "tags": meta["tags"], "cid": meta["cid"]}
                for mid, meta in memory_index.items()
                if any(query in tag.lower() for tag in meta["tags"])
                or query in meta.get("preview", "").lower()
            ]
        return {"results": results, "count": len(results)}

    raise ValueError(f"Unknown tool: {tool}")


# ── REST endpoints ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name": "DAMN Memory",
        "version": "2.2",
        "mcp_endpoint": "/mcp",
        "health": "/health",
    }


@app.get("/health")
def health():
    # local IPFS node
    local_ok, repo_size = False, None
    try:
        r = requests.post(f"{LOCAL_IPFS_API}/api/v0/repo/stat", timeout=5)
        if r.status_code == 200:
            local_ok = True
            repo_size = r.json().get("RepoSize")
    except requests.RequestException:
        pass

    # Pinata
    pinata_ok, pin_count = False, -1
    if PINATA_JWT:
        try:
            r = requests.get(
                "https://api.pinata.cloud/data/testAuthentication",
                headers=PINATA_HEADERS,
                timeout=5,
            )
            pinata_ok = r.status_code == 200
        except requests.RequestException:
            pass
        try:
            pins = requests.get(
                "https://api.pinata.cloud/data/pinList?status=pinned&pageLimit=1",
                headers=PINATA_HEADERS,
                timeout=5,
            )
            pin_count = pins.json().get("count", 0)
        except (requests.RequestException, ValueError):
            pass

    with _index_lock:
        cached = len(memory_index)

    return {
        "status": "running",
        "memories_cached": cached,
        "storage": "hybrid: local IPFS node + Pinata backup",
        "local_ipfs_connected": local_ok,
        "local_ipfs_repo_bytes": repo_size,
        "pinata_connected": pinata_ok,
        "pinata_pins_used": pin_count,
        "pinata_pins_limit": 500,
        "chain": "coming_soon",
    }


@app.get("/tools")
def list_tools():
    return {"tools": [{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS]}


@app.post("/tools/store_memory")
async def store_memory_rest(req: StoreMemoryRequest):
    return await run_in_threadpool(
        handle_tool, "store_memory", {"content": req.content, "tags": req.tags}
    )


@app.post("/tools/retrieve_memory")
async def retrieve_memory_rest(req: RetrieveMemoryRequest):
    return await run_in_threadpool(handle_tool, "retrieve_memory", {"memory_id": req.memory_id})


@app.get("/tools/list_memories")
async def list_memories_rest():
    return await run_in_threadpool(handle_tool, "list_memories", {})


@app.post("/tools/search_memories")
async def search_memories_rest(req: SearchMemoryRequest):
    return await run_in_threadpool(handle_tool, "search_memories", {"query": req.query})
