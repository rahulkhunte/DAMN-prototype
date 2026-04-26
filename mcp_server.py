"""
DAMN MCP Server — exposes DAMN as a tool for OpenClaw, LangChain, AutoGen
Run: uvicorn mcp_server:app --host 0.0.0.0 --port 8000
"""
import os, hashlib, requests, time
from fastapi import FastAPI
from pydantic import BaseModel
from web3 import Web3
from dotenv import load_dotenv
import json

load_dotenv()

app = FastAPI(title="DAMN MCP Server", version="1.0.0")

# --- Config ---
w3 = Web3(Web3.HTTPProvider(os.getenv("POLYGON_RPC", "https://polygon-rpc.com")))
PINATA_KEY    = os.getenv("PINATA_API_KEY")
PINATA_SECRET = os.getenv("PINATA_API_SECRET")
CONTRACT_ADDR = os.getenv("CONTRACT_ADDRESS_POLYGON")
PRIVATE_KEY   = os.getenv("PRIVATE_KEY")
account       = w3.eth.account.from_key(PRIVATE_KEY)

# Minimal ABI — only what MCP needs
ABI = [
    {"inputs":[{"type":"bytes32"},{"type":"string"},{"type":"string"},{"type":"string"}],
     "name":"storeMemory","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"type":"bytes32"}],"name":"retrieveMemory",
     "outputs":[{"type":"string"}],"stateMutability":"view","type":"function"}
]
contract = w3.eth.contract(address=CONTRACT_ADDR, abi=ABI)

def to_bytes32(agent_id: str, ts: int) -> bytes:
    return hashlib.sha256(f"{agent_id}_{ts}".encode()).digest()

def ipfs_pin(data: dict, name: str) -> str:
    r = requests.post("https://api.pinata.cloud/pinning/pinJSONToIPFS",
        json={"pinataContent": data, "pinataMetadata": {"name": name}},
        headers={"pinata_api_key": PINATA_KEY,
                 "pinata_secret_api_key": PINATA_SECRET})
    return r.json()["IpfsHash"]

def ipfs_get(cid: str) -> dict:
    return requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}").json()

# --- MCP Tool Models ---
class StoreRequest(BaseModel):
    agent_id: str
    content: dict
    task_type: str = "general"

class RecallRequest(BaseModel):
    agent_id: str
    timestamp: int  # unix ts of the memory to recall

# --- MCP Endpoints (tools) ---
@app.get("/tools")
def list_tools():
    """MCP tool manifest — OpenClaw reads this"""
    return {"tools": [
        {"name": "remember", "description": "Store agent memory on IPFS + Polygon blockchain",
         "input_schema": StoreRequest.schema()},
        {"name": "recall",   "description": "Retrieve agent memory by agent_id + timestamp",
         "input_schema": RecallRequest.schema()}
    ]}

@app.post("/tools/remember")
def remember(req: StoreRequest):
    """Store memory — costs ~$0.001 gas on Polygon"""
    ts  = int(time.time())
    cid = ipfs_pin({"agent_id": req.agent_id, "data": req.content,
                    "task": req.task_type, "ts": ts}, req.agent_id)
    mem_id = to_bytes32(req.agent_id, ts)

    nonce = w3.eth.get_transaction_count(account.address)
    txn   = contract.functions.storeMemory(
        mem_id, cid, req.agent_id, req.task_type
    ).build_transaction({
        "from": account.address, "nonce": nonce,
        "gas": 200000, "gasPrice": w3.eth.gas_price, "chainId": 137
    })
    signed = account.sign_transaction(txn)
    tx     = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=120)

    return {"status": "stored", "cid": cid,
            "tx": tx.hex(), "gas_used": receipt["gasUsed"]}

@app.post("/tools/recall")
def recall(req: RecallRequest):
    """Recall memory — FREE, no gas"""
    mem_id = to_bytes32(req.agent_id, req.timestamp)
    cid    = contract.functions.retrieveMemory(mem_id).call()
    if not cid:
        return {"status": "not_found"}
    data = ipfs_get(cid)
    return {"status": "found", "cid": cid, "memory": data}

@app.get("/health")
def health():
    return {"status": "ok", "chain": "polygon",
            "block": w3.eth.block_number, "contract": CONTRACT_ADDR}