"""API Tests for Task Ingestion and Status."""
import asyncio
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(async_client: AsyncClient):
    # Health probe
    res_h = await async_client.get("/api/v1/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "healthy"

    # Readiness probe
    res_r = await async_client.get("/api/v1/ready")
    assert res_r.status_code == 200
    assert res_r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_task_creation_and_status_polling(async_client: AsyncClient):
    payload = {
        "objective": "Calculate multiplication for baseline performance metric: 125 * 8",
        "parameters": {},
        "max_execution_seconds": 60
    }
    headers = {"X-API-Key": "test-key-123"}

    # Ingest task
    create_res = await async_client.post("/api/v1/tasks", json=payload, headers=headers)
    assert create_res.status_code == 202
    data = create_res.json()
    task_id = data["task_id"]
    assert data["status"] == "SUBMITTED"

    # Poll status (give background task a short moment to initialize)
    await asyncio.sleep(0.5)
    status_res = await async_client.get(f"/api/v1/tasks/{task_id}/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["task_id"] == task_id


@pytest.mark.asyncio
async def test_task_idempotency(async_client: AsyncClient):
    idempotency_key = f"idemp-{uuid.uuid4()}"
    payload = {
        "objective": "Research vector database options for RAG",
        "parameters": {}
    }
    headers = {
        "X-API-Key": "test-user-idemp",
        "Idempotency-Key": idempotency_key
    }

    # First submission
    res1 = await async_client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res1.status_code == 202
    task_id1 = res1.json()["task_id"]

    # Second submission with same Idempotency-Key
    res2 = await async_client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res2.status_code == 202
    task_id2 = res2.json()["task_id"]

    # Must return exact same task_id
    assert task_id1 == task_id2
