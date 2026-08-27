from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("saic")


class Settings(BaseSettings):
    app_name: str = "SAIC - Secure Autonomous Incident Commander"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://localhost:5173"

    lyzr_api_key: str = ""
    lyzr_agent_id: str = "6a8e92136b34b4bdbc975052"
    lyzr_chat_url: str = ""

    qdrant_mode: Literal["local", "remote"] = "local"
    qdrant_path: str = "./storage/qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "saic_incident_memory"

    saic_memory_vector_dim: int = 384
    saic_memory_top_k: int = 5
    saic_local_safety_mode: Literal["simulated", "strict"] = "simulated"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


settings = Settings()


class SaicChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    incident_id: str | None = None
    service_name: str | None = None
    environment: str = "simulation"


class MemorySeedRequest(BaseModel):
    content: str = Field(min_length=1)
    session_id: str = "seed"
    user_id: str = "system"
    incident_id: str | None = None
    service_name: str | None = None
    environment: str = "simulation"
    source: str = "manual"


class MemoryHit(BaseModel):
    text: str
    score: float
    payload: dict[str, Any]


class SaicChatResponse(BaseModel):
    status: str
    safety_decision: Literal["allow", "block"]
    answer: str
    session_id: str
    user_id: str
    incident_id: str | None = None
    service_name: str | None = None
    retrieved_context: list[MemoryHit] = Field(default_factory=list)
    memory_saved: bool = False
    agent_source: Literal["lyzr", "local-fallback"] = "local-fallback"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _hash_embedding(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (len(token) / 10.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_safety_decision(request: SaicChatRequest) -> tuple[Literal["allow", "block"], str]:
    text = _normalize_text(" ".join([request.message, request.service_name or "", request.environment or ""]))
    blocked_terms = ["production", "prod", "live", "delete", "destroy", "wipe", "drop", "terminate", "shutdown"]

    if settings.saic_local_safety_mode == "strict" and any(term in text for term in blocked_terms):
        return "block", "Strict mode blocks production-style or destructive requests."

    if any(term in text for term in blocked_terms) and "sim" not in text and "test" not in text:
        return "block", "SAIC is configured for simulated incidents only."

    return "allow", "Allowed for simulated incident handling."


def _memory_doc(
    *,
    role: str,
    text: str,
    session_id: str,
    user_id: str,
    incident_id: str | None,
    service_name: str | None,
    environment: str,
    source: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "text": text,
        "session_id": session_id,
        "user_id": user_id,
        "incident_id": incident_id or "",
        "service_name": service_name or "",
        "environment": environment,
        "source": source,
        "created_at": _utc_now(),
    }


class SaicMemoryStore:
    def __init__(self) -> None:
        self.collection_name = settings.qdrant_collection
        self.dim = settings.saic_memory_vector_dim

        if settings.qdrant_mode == "remote":
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                timeout=30.0,
            )
        else:
            Path(settings.qdrant_path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=settings.qdrant_path)

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
        )

    def search(self, query: str, top_k: int | None = None) -> list[MemoryHit]:
        if not query.strip():
            return []

        self.ensure_collection()
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=_hash_embedding(query, self.dim),
            limit=top_k or settings.saic_memory_top_k,
            with_payload=True,
        )

        results: list[MemoryHit] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            results.append(
                MemoryHit(
                    text=str(payload.get("text", "")),
                    score=float(hit.score or 0.0),
                    payload=payload,
                )
            )
        return results

    def store(
        self,
        *,
        role: str,
        text: str,
        session_id: str,
        user_id: str,
        incident_id: str | None,
        service_name: str | None,
        environment: str,
        source: str,
    ) -> str:
        self.ensure_collection()
        point_id = str(uuid.uuid4())
        payload = _memory_doc(
            role=role,
            text=text,
            session_id=session_id,
            user_id=user_id,
            incident_id=incident_id,
            service_name=service_name,
            environment=environment,
            source=source,
        )
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=_hash_embedding(text, self.dim),
                    payload=payload,
                )
            ],
        )
        return point_id


memory_store = SaicMemoryStore()


def _build_prompt(request: SaicChatRequest, retrieved: list[MemoryHit]) -> str:
    memory_lines = []
    for index, hit in enumerate(retrieved, start=1):
        snippet = hit.text.strip().replace("\n", " ")
        if len(snippet) > 500:
            snippet = snippet[:497] + "..."
        memory_lines.append(f"{index}. {snippet}")

    memory_block = "\n".join(memory_lines) if memory_lines else "No relevant memory found."

    return (
        "You are SAIC, the Secure Autonomous Incident Commander.\n"
        "Work only on simulated incidents.\n"
        "If critical data is missing, ask for telemetry.\n"
        "Be direct, safe, and short.\n\n"
        f"Session ID: {request.session_id}\n"
        f"User ID: {request.user_id}\n"
        f"Incident ID: {request.incident_id or 'not provided'}\n"
        f"Service Name: {request.service_name or 'not provided'}\n"
        f"Environment: {request.environment}\n\n"
        f"Relevant memory:\n{memory_block}\n\n"
        f"User message:\n{request.message}"
    )


def _fallback_answer(request: SaicChatRequest, retrieved: list[MemoryHit]) -> str:
    if retrieved:
        return "I found relevant memory, but Lyzr is not configured yet. Add LYZR_API_KEY, LYZR_AGENT_ID, and LYZR_CHAT_URL."
    return "I need the simulated service name and telemetry/logs/traces before I can determine root cause safely."


def _call_lyzr(request: SaicChatRequest, prompt: str, retrieved: list[MemoryHit]) -> tuple[str, str]:
    if not (settings.lyzr_api_key and settings.lyzr_agent_id and settings.lyzr_chat_url):
        return _fallback_answer(request, retrieved), "local-fallback"

    payload = {
        "agent_id": settings.lyzr_agent_id,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "message": prompt,
    }
    headers = {
        "x-api-key": settings.lyzr_api_key,
        "content-type": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(settings.lyzr_chat_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.exception("Lyzr call failed: %s", exc)
        return _fallback_answer(request, retrieved), "local-fallback"

    if isinstance(data, dict):
        for key in ("answer", "response", "message", "text", "output"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip(), "lyzr"
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("answer", "response", "message", "text", "output"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip(), "lyzr"
        return json.dumps(data, indent=2), "lyzr"

    return str(data), "lyzr"


app = FastAPI(title=settings.app_name, version="0.1.0", openapi_url=f"{settings.api_v1_prefix}/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get(f"{settings.api_v1_prefix}/saic/status")
def saic_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_collection": settings.qdrant_collection,
        "lyzr_ready": bool(settings.lyzr_api_key and settings.lyzr_agent_id and settings.lyzr_chat_url),
        "safety_mode": settings.saic_local_safety_mode,
    }


@app.post(f"{settings.api_v1_prefix}/saic/seed")
def seed_memory(request: MemorySeedRequest) -> dict[str, Any]:
    memory_id = memory_store.store(
        role="memory",
        text=request.content,
        session_id=request.session_id,
        user_id=request.user_id,
        incident_id=request.incident_id,
        service_name=request.service_name,
        environment=request.environment,
        source=request.source,
    )
    return {"status": "ok", "memory_id": memory_id}


@app.post(f"{settings.api_v1_prefix}/saic/chat", response_model=SaicChatResponse)
def saic_chat(request: SaicChatRequest) -> SaicChatResponse:
    safety_decision, safety_reason = _build_safety_decision(request)
    if safety_decision == "block":
        return SaicChatResponse(
            status="blocked",
            safety_decision="block",
            answer=safety_reason,
            session_id=request.session_id,
            user_id=request.user_id,
            incident_id=request.incident_id,
            service_name=request.service_name,
            retrieved_context=[],
            memory_saved=False,
            agent_source="local-fallback",
        )

    query_text = " ".join(
        part for part in [request.message, request.incident_id or "", request.service_name or "", request.environment or ""] if part
    )
    retrieved = memory_store.search(query_text, top_k=settings.saic_memory_top_k)
    prompt = _build_prompt(request, retrieved)
    answer, source = _call_lyzr(request, prompt, retrieved)

    memory_saved = False
    try:
        memory_store.store(
            role="user",
            text=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            incident_id=request.incident_id,
            service_name=request.service_name,
            environment=request.environment,
            source="chat:user",
        )
        memory_store.store(
            role="assistant",
            text=answer,
            session_id=request.session_id,
            user_id=request.user_id,
            incident_id=request.incident_id,
            service_name=request.service_name,
            environment=request.environment,
            source="chat:assistant",
        )
        memory_saved = True
    except Exception as exc:
        logger.warning("Could not persist memory: %s", exc)

    return SaicChatResponse(
        status="ok",
        safety_decision="allow",
        answer=answer,
        session_id=request.session_id,
        user_id=request.user_id,
        incident_id=request.incident_id,
        service_name=request.service_name,
        retrieved_context=retrieved,
        memory_saved=memory_saved,
        agent_source=source,
    )