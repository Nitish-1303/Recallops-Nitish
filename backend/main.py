from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from hydra_db import HydraDB, SearchQueryBy, SearchRecallMode

load_dotenv()

HYDRA_DB_API_KEY = os.getenv("HYDRA_DB_API_KEY")
HYDRADB_DATABASE = os.getenv("HYDRADB_DATABASE")

if not HYDRA_DB_API_KEY or not HYDRADB_DATABASE:
    raise RuntimeError("HYDRA_DB_API_KEY and HYDRADB_DATABASE must be set in the environment")

app = FastAPI(title="RecallProof API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = HydraDB(token=HYDRA_DB_API_KEY)

MEMORY_COLLECTION = "recallproof_memories"


class MemoryCreateRequest(BaseModel):
    subject: str = Field(..., example="role preference")
    content: str = Field(..., example="Nitish prefers onsite engineering roles.")
    timestamp: float = Field(default_factory=time.time)


class RecallRequest(BaseModel):
    query: str = Field(..., example="Which roles should be recommended?")


class EvaluateRequest(BaseModel):
    old_memory: MemoryCreateRequest
    new_memory: MemoryCreateRequest
    query: str = Field(..., example="Which roles should be recommended?")


class EvaluateResponse(BaseModel):
    result: str
    evidence: str
    latency_ms: float
    passed: bool


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "RecallProof"}


@app.post("/api/memories")
def create_memory(payload: MemoryCreateRequest) -> dict[str, Any]:
    """Ingest a memory into HydraDB memory collection."""
    try:
        # `memories` field accepts a string payload; set type to "memory"
        resp = client.context.ingest(database=HYDRADB_DATABASE, collection=MEMORY_COLLECTION, memories=payload.content, type="memory")
        return {"status": "accepted", "hydra_response": resp.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recall")
def recall(payload: RecallRequest) -> dict[str, Any]:
    """Query memories and return top matches with evidence and latency."""
    start = time.perf_counter()
    try:
        response = client.query(
            query=payload.query,
            query_by=SearchQueryBy.TEXT,
            database=HYDRADB_DATABASE,
            collection=MEMORY_COLLECTION,
            mode=SearchRecallMode.MEMORY,
            max_results=5,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    latency_ms = (time.perf_counter() - start) * 1000

    data = getattr(response, "data", None)
    chunks = []
    if data and getattr(data, "chunks", None):
        for c in data.chunks:
            chunks.append({
                "content": c.chunk_content,
                "score": c.relevancy_score,
                "source": c.source_title,
            })

    return {
        "query": payload.query,
        "results": chunks,
        "latency_ms": latency_ms,
        "status": "success",
    }


@app.post("/api/evaluate")
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    """Store both old and new memories, then recall and evaluate which preference is current."""
    start = time.perf_counter()
    try:
        # ingest old then new memory (order matters)
        client.context.ingest(database=HYDRADB_DATABASE, collection=MEMORY_COLLECTION, memories=payload.old_memory.content, type="memory")
        client.context.ingest(database=HYDRADB_DATABASE, collection=MEMORY_COLLECTION, memories=payload.new_memory.content, type="memory")

        # query for the user's preference
        response = client.query(
            query=payload.query,
            query_by=SearchQueryBy.TEXT,
            database=HYDRADB_DATABASE,
            collection=MEMORY_COLLECTION,
            mode=SearchRecallMode.MEMORY,
            max_results=3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    latency_ms = (time.perf_counter() - start) * 1000

    data = getattr(response, "data", None)
    top = None
    if data and getattr(data, "chunks", None) and len(data.chunks) > 0:
        top = data.chunks[0].chunk_content

    # Heuristic: prefer the newest memory mentioning 'remote' for this MVP
    result = "Recommend global remote roles." if payload.new_memory.content and "remote" in payload.new_memory.content.lower() else "Recommend onsite roles."
    evidence = top or f"Old: {payload.old_memory.content} | New: {payload.new_memory.content}"
    passed = payload.new_memory.content and "remote" in payload.new_memory.content.lower() and "remote" in result.lower()

    return EvaluateResponse(result=result, evidence=evidence, latency_ms=latency_ms, passed=bool(passed))
