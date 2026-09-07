```markdown
# SAIC - Secure Autonomous Incident Commander

An AI-powered incident response system for safe DevOps incident triage, memory retrieval, and intelligent remediation recommendations in a fully simulated environment.

## 🎯 Project Purpose

SAIC helps DevOps teams investigate production incidents safely by analyzing incident reports with AI reasoning, retrieving relevant historical incidents from memory, suggesting remediation steps without touching real systems, and learning from past incidents for better future responses.

## ✨ Features

- Real-time incident analysis with Lyzr AI
- Vector-based incident memory with Qdrant
- Safety validation for simulated-only operations
- Structured JSON responses for integration
- Interactive web UI for incident reporting
- RESTful API for programmatic access
- Render cloud deployment ready

## 🏗️ Architecture

**Tech Stack:** FastAPI backend, Lyzr Agent API for AI reasoning, Qdrant Cloud for vector memory storage, Render.com for hosting, HTML/CSS/JavaScript frontend.

SAIC follows this workflow: Report → Analyze → Retrieve Context → Reason → Validate → Recommend → Learn

## 🚀 Quick Start

```bash
git clone https://github.com/sanjayk16-07/saic-secure-autonomous-incident-commander
cd saic-agent
pip install -r requirements.txt
cp .env.example .env
# Add your Lyzr API key and Qdrant Cloud credentials
python -m uvicorn main:app --reload
```

Visit: `http://localhost:8000` or `https://saic-agent.onrender.com`

## 📡 API Endpoints

**Health Check:** `GET /health`

**Get Status:** `GET /api/v1/saic/status`

**Seed Memory:** `POST /api/v1/saic/seed`

**Chat/Analyze Incident:** `POST /api/v1/saic/chat`

Example request:
```json
{
  "message": "Database connection timeout on payment service",
  "session_id": "saic-demo-001",
  "user_id": "ksanj",
  "incident_id": "INC-001",
  "service_name": "checkout",
  "environment": "simulation"
}
```

## 🔧 Configuration

Set environment variables in `.env`:
- `LYZR_API_KEY` - Your Lyzr API key
- `LYZR_AGENT_ID` - Your Lyzr agent ID
- `LYZR_CHAT_URL` - https://agent-prod.studio.lyzr.ai/v3/inference/chat/
- `QDRANT_MODE` - remote
- `QDRANT_URL` - Your Qdrant Cloud URL
- `QDRANT_API_KEY` - Your Qdrant API key

## 📝 Example Incidents to Test

1. "Database connection timeout on payment service"
2. "API response time increased 500% after latest deploy"
3. "Memory leak detected consuming 95% RAM"
4. "Sudden spike in 5xx errors on auth service"
5. "Cache miss rate jumped from 2% to 45%"

## 🔐 Security

- Simulated-only mode (never executes real remediation)
- Local safety gate validation
- API key protection via environment variables
- Qdrant Cloud encryption
- CORS-enabled for web UI

## 📚 Technology Decisions

**Lyzr AI:** Provides advanced reasoning and natural language understanding for incident analysis. **Qdrant:** Enables vector similarity search for retrieving relevant past incidents. **FastAPI:** High-performance async web framework for real-time incident processing. **Render:** Serverless hosting with automatic GitHub deployments.

## 🎯 Future Enhancements

- WebSocket support for real-time streaming
- Integration with monitoring tools (Prometheus, DataDog)
- Multi-language incident reports
- Advanced analytics dashboard
- Automated runbook execution

## 📄 License

MIT

---

**Live:** https://saic-agent.onrender.com  
**Repo:** https://github.com/sanjayk16-07/saic-secure-autonomous-incident-commander
```

Copy-paste ready! 🚀