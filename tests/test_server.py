"""Unit tests for the DAMN MCP server. IPFS calls are mocked — no network needed."""
import json
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["INDEX_FILE"] = os.path.join(tempfile.mkdtemp(), "test_index.json")
os.environ.setdefault("AGENTICMARKET_SECRET", "test-secret")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server  # noqa: E402

FAKE_CID = "bafkreifaketestcid0000000000000000000000000000000000000000"


@pytest.fixture(autouse=True)
def mock_ipfs(monkeypatch):
    stored = {}

    def fake_pin_local(data):
        stored[FAKE_CID] = data
        return FAKE_CID

    def fake_fetch(cid):
        return stored[cid]

    monkeypatch.setattr(mcp_server, "pin_to_local_node", fake_pin_local)
    monkeypatch.setattr(mcp_server, "pin_to_pinata", lambda data: None)
    monkeypatch.setattr(mcp_server, "fetch_from_ipfs", fake_fetch)
    mcp_server.memory_index.clear()
    yield


@pytest.fixture
def client():
    # TestClient connects from "testclient" host — not localhost — so requests
    # exercise the auth middleware unless the secret header is sent.
    return TestClient(mcp_server.app)


AUTH = {"X-AgenticMarket-Secret": os.environ["AGENTICMARKET_SECRET"]}


def test_open_endpoints_need_no_auth(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/tools").status_code == 200


def test_protected_endpoint_rejects_missing_secret(client):
    r = client.post("/tools/store_memory", json={"content": "x"})
    assert r.status_code == 401


def test_protected_endpoint_rejects_wrong_secret(client):
    r = client.post(
        "/tools/store_memory",
        json={"content": "x"},
        headers={"X-AgenticMarket-Secret": "wrong"},
    )
    assert r.status_code == 401


def test_store_and_retrieve_roundtrip(client):
    r = client.post(
        "/tools/store_memory",
        json={"content": "UAV-001 learned climb_to_200m", "tags": ["uav", "nav"]},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ipfs_cid"] == FAKE_CID
    assert body["pinned_local"] is True
    mid = body["memory_id"]

    r = client.post("/tools/retrieve_memory", json={"memory_id": mid}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["data"]["content"] == "UAV-001 learned climb_to_200m"


def test_memory_ids_unique_same_second(client):
    ids = set()
    for _ in range(5):
        r = client.post("/tools/store_memory", json={"content": "x"}, headers=AUTH)
        ids.add(r.json()["memory_id"])
    assert len(ids) == 5


def test_search_matches_tags_and_content(client):
    client.post(
        "/tools/store_memory",
        json={"content": "obstacle at sector 7", "tags": ["nav"]},
        headers=AUTH,
    )
    by_tag = client.post("/tools/search_memories", json={"query": "nav"}, headers=AUTH).json()
    assert by_tag["count"] == 1
    by_content = client.post(
        "/tools/search_memories", json={"query": "sector 7"}, headers=AUTH
    ).json()
    assert by_content["count"] == 1


def test_retrieve_unknown_memory(client):
    r = client.post("/tools/retrieve_memory", json={"memory_id": "mem_nope"}, headers=AUTH)
    assert "error" in r.json()


def test_mcp_initialize_and_tools_list(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 7, "method": "initialize"})
    assert r.json()["id"] == 7
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
    assert len(r.json()["result"]["tools"]) == 4


def test_mcp_notification_returns_no_body(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert r.status_code == 202
    assert r.content == b""


def test_mcp_tool_call_returns_valid_json_text(client):
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "store_memory", "arguments": {"content": "hello"}},
        },
        headers=AUTH,
    )
    text = r.json()["result"]["content"][0]["text"]
    parsed = json.loads(text)  # must be real JSON, not Python repr
    assert parsed["ipfs_cid"] == FAKE_CID


def test_mcp_tool_call_requires_auth(client):
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "list_memories", "arguments": {}}},
    )
    assert r.json()["error"]["code"] == -32001


def test_mcp_unknown_method(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "bogus"})
    assert r.json()["error"]["code"] == -32601


def test_mcp_unknown_tool(client):
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "nope", "arguments": {}}},
        headers=AUTH,
    )
    assert r.json()["error"]["code"] == -32602


def test_index_persists_to_disk(client):
    client.post("/tools/store_memory", json={"content": "persist me"}, headers=AUTH)
    with open(os.environ["INDEX_FILE"]) as f:
        on_disk = json.load(f)
    assert len(on_disk) == 1
