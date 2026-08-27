# saic-secure-autonomous-incident-commander
SAIC is a secure autonomous incident commander for simulated DevOps incident triage, memory retrieval, and safe remediation using Lyzr and Qdrant.


# Secure Autonomous Incident Commander (SAIC)

Secure Autonomous Incident Commander (SAIC) is an AI agent for safe DevOps incident triage and remediation in a fully simulated environment. It observes telemetry, retrieves incident memory, reasons over the situation, validates safety, and returns a structured response.

## Project Purpose

SAIC is designed to help investigate incidents safely, use past incident memory for context, and suggest or simulate remediation steps without touching real production systems.

## Features

- Incident triage
- Memory retrieval from Qdrant
- Safe simulated remediation workflow
- Structured JSON responses
- Lyzr agent integration
- Render deployment support

## How It Works

SAIC follows this lifecycle:

`Observe -> Investigate -> Retrieve -> Reason -> Validate -> Act -> Verify -> Learn`

## Architecture

- **Lyzr**: agent reasoning and orchestration
- **Qdrant**: incident memory and retrieval
- **FastAPI**: backend API
- **Render**: backend hosting
- **Thunder Client / API client**: testing endpoints

## API Endpoints

### Health
`GET /health`

### Seed Memory
`POST /api/v1/saic/seed`

### Chat
`POST /api/v1/saic/chat`

## Example Request: Seed

```json
{
  "content": "Incident INC-001: checkout latency increased after deploy.",
  "session_id": "saic-demo-001",
  "user_id": "ksanj",
  "incident_id": "INC-001",
  "service_name": "checkout",
  "environment": "simulation",
  "source": "manual"
}
