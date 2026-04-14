# 🔍 Ask-the-Web Agent

> **Perplexity-style AI research agent** — real-time web search, multi-step reasoning, source citations, and streaming responses. Built with Claude Sonnet, FastAPI, and React.

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue?logo=react)](https://react.dev)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-orange)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Real-time web search** | Tavily + SerpAPI with automatic fallback |
| 🧠 **ReACT reasoning** | Thought → Action → Observation loop |
| 📚 **Source citations** | Every claim linked to its source URL |
| ⚡ **Streaming answers** | Token-by-token streaming via SSE |
| 🔄 **Reflection** | Self-critique and answer improvement |
| 🤝 **Multi-agent system** | Research + Summarizer + Fact-Checker agents |
| 📊 **Quality evaluation** | Relevance, hallucination risk, source diversity |
| 💾 **Session memory** | Short-term (in-memory) + long-term (PostgreSQL) |
| 🐳 **Docker-ready** | One-command deployment |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│          React + Vite + Tailwind  (port 5173)               │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTP / SSE / WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend  (port 8000)              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              OrchestratorAgent                       │   │
│  │   ┌──────────┐  ┌─────────────┐  ┌──────────────┐  │   │
│  │   │ Research │  │ Summarizer  │  │ FactChecker  │  │   │
│  │   │  Agent   │  │   Agent     │  │    Agent     │  │   │
│  │   └────┬─────┘  └─────────────┘  └──────────────┘  │   │
│  └────────┼────────────────────────────────────────────┘   │
│           │                                                 │
│  ┌────────▼────────────────────────────────────────────┐   │
│  │              Workflow Engine                          │   │
│  │  Chaining │ Routing │ Parallelization │ Reflection   │   │
│  └────────────────────────────────────────────────────-┘   │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │     Tool Registry    │  │       Memory              │   │
│  │  web_search          │  │  Short-term (in-memory)   │   │
│  │  extract_content     │  │  Long-term (PostgreSQL)   │   │
│  └──────────┬───────────┘  └──────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────────────────────────────────────┐  │
│  │                  MCP Client Layer                      │  │
│  │  MCP Server A (Search)  │  MCP Server B (Database)   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                              │
   ┌─────▼──────┐               ┌───────▼───────┐
   │  Tavily /  │               │  PostgreSQL   │
   │  SerpAPI   │               │  + pgvector   │
   └────────────┘               └───────────────┘
```

### Agency Levels Implemented

| Level | Pattern | Implementation |
|---|---|---|
| **1 — Simple** | Direct LLM call | `BaseAgent.run()` for conversational queries |
| **2 — Multi-step** | ReACT loop | Tool-use loop with up to 10 iterations |
| **3 — Autonomous** | Orchestrator-Worker | `OrchestratorAgent` plans, delegates, evaluates |

---

## 📁 Project Structure

```
ask-the-web-agent/
├── backend/
│   ├── main.py                  # FastAPI app + all routes
│   ├── config.py                # Centralised settings (pydantic-settings)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── agents/
│   │   ├── base_agent.py        # ReACT loop + reflection + streaming
│   │   ├── research_agent.py    # Multi-angle parallel research
│   │   ├── summarizer_agent.py  # Condenses long research
│   │   ├── fact_checker_agent.py# Cross-verifies key claims
│   │   └── orchestrator.py      # Planner → Workers → Validator
│   ├── workflows/
│   │   └── chains.py            # Chaining, routing, parallel, reflection, O-W
│   ├── tools/
│   │   ├── tool_registry.py     # JSON-schema registry + async executor
│   │   ├── web_search.py        # Tavily / SerpAPI / stub
│   │   └── content_extractor.py # URL → cleaned text
│   ├── memory/
│   │   ├── short_term.py        # Per-session rolling window
│   │   └── long_term.py         # PostgreSQL-backed persistent facts
│   ├── mcp/
│   │   └── mcp_client.py        # MCP JSON-RPC client + server registry
│   ├── evaluation/
│   │   └── evaluator.py         # Relevance, citation, hallucination scores
│   └── tests/
│       └── test_agent.py        # pytest suite (37 tests)
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Root layout
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── SearchBar.jsx    # Animated input with suggestions
│   │   │   ├── ThinkingPanel.jsx# Live agent progress
│   │   │   ├── AnswerPanel.jsx  # Streaming markdown renderer
│   │   │   ├── SourcesPanel.jsx # Clickable citation cards
│   │   │   ├── EvaluationBadge.jsx # Quality score display
│   │   │   └── HistoryDrawer.jsx# Slide-in session history
│   │   ├── hooks/
│   │   │   └── useSearch.js     # Central state machine
│   │   ├── utils/
│   │   │   └── api.js           # Fetch-based API client + SSE streaming
│   │   └── styles/
│   │       └── globals.css      # Tailwind + dark theme + prose
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### Option A — Local (recommended for development)

#### 1. Clone and configure

```bash
git clone https://github.com/yourusername/ask-the-web-agent.git
cd ask-the-web-agent
cp .env.example .env
# Edit .env and add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   TAVILY_API_KEY=tvly-...    ← get free key at https://tavily.com
```

#### 2. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env      # copy keys into backend/.env too
uvicorn main:app --reload --port 8000
```

> The server starts at **http://localhost:8000**
> Swagger UI: **http://localhost:8000/docs** (when DEBUG=true)

#### 3. Frontend setup

```bash
# In a new terminal
cd frontend
npm install
npm run dev
```

> App opens at **http://localhost:5173**

---

### Option B — Docker Compose (one command)

```bash
# 1. Set your keys
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and TAVILY_API_KEY

# 2. Launch everything
docker-compose up --build

# App:     http://localhost:5173
# API:     http://localhost:8000
# PgAdmin: connect to localhost:5432
```

---

## 🔌 API Reference

### `POST /api/search` — Full orchestrated search

```json
// Request
{
  "query": "What are the latest breakthroughs in quantum computing?",
  "session_id": "optional-uuid-for-multi-turn",
  "route": null
}

// Response
{
  "answer": "## Quantum Computing Breakthroughs...\n\n[Source: https://...]",
  "sources": [
    {"title": "Google Quantum AI", "url": "https://quantumai.google/..."}
  ],
  "evaluation": {
    "overall": 0.87,
    "relevance": 0.92,
    "hallucination_risk": "low",
    "source_count": 4,
    "latency_ms": 3240
  },
  "route": "deep",
  "latency_ms": 3240.5,
  "agent": "OrchestratorAgent"
}
```

### `POST /api/stream` — Streaming SSE

```javascript
// Each SSE event is one of:
{ "type": "thinking", "content": "🔍 Searching: **quantum computing 2025**" }
{ "type": "text",     "content": "## Quantum Computing..." }
{ "type": "source",   "content": { "title": "...", "url": "..." } }
{ "type": "evaluation","content": { "overall": 0.87, ... } }
{ "type": "done",     "content": { "sources": [...], "iterations": 3 } }
```

### `DELETE /api/session/{session_id}` — Clear memory

### `GET /api/health` — Health check

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=html
```

---

## 📝 Example Queries & Expected Behaviour

| Query | Route | Agents Used | ~Latency |
|---|---|---|---|
| "What is 2+2?" | simple | BaseAgent | ~0.5s |
| "Latest AI research 2025" | deep | Research + Summarizer | ~6s |
| "Is GPT-4 better than Claude?" | deep | Research + Summarizer | ~8s |
| "Fact check: humans only use 10% of their brain" | factual | Research + FactChecker | ~9s |
| "What's the weather in Mumbai?" | simple | BaseAgent + search | ~2s |

---

## 🧠 Architecture Concepts Explained

### LLM vs Agent vs Agentic System

| Concept | Definition | Example in this project |
|---|---|---|
| **LLM** | Stateless text predictor; one call, one response | Direct `claude.messages.create()` call |
| **Agent** | LLM + tools + loop; can take actions | `BaseAgent.run()` — ReACT loop |
| **Agentic System** | Multiple agents + orchestration + memory | `OrchestratorAgent` coordinating 3 sub-agents |

### Workflow Patterns

- **Prompt Chaining** → `workflows/chains.py:prompt_chain()` — research → summarize → format
- **Routing** → `agents/orchestrator.py:_decide_route()` — classifies query into simple/deep/factual
- **Parallelization** → `agents/research_agent.py:run_parallel_research()` — 3 searches simultaneously
- **Reflection** → `agents/base_agent.py:_reflect()` — self-critique loop
- **Orchestrator-Worker** → `agents/orchestrator.py:process()` — Planner → Executor → Validator

---

## 🔧 Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Claude API key |
| `TAVILY_API_KEY` | ⚡ | — | Primary search (recommended) |
| `SERPAPI_KEY` | ⚡ | — | Fallback search |
| `DATABASE_URL` | ❌ | — | PostgreSQL for long-term memory |
| `REDIS_URL` | ❌ | — | Response caching |
| `MAX_AGENT_ITERATIONS` | ❌ | 10 | ReACT loop cap |
| `REFLECTION_ENABLED` | ❌ | true | Enable self-critique pass |
| `CLAUDE_MODEL` | ❌ | claude-sonnet-4-6 | Model to use |

⚡ At least one search API key is strongly recommended. Without one, stub results are returned.

---

## 📈 Extending the Project

### Add a new tool

```python
# backend/tools/my_tool.py
from tools.tool_registry import ToolDefinition, registry

async def my_tool(query: str) -> dict:
    return {"result": f"processed: {query}"}

registry.register(ToolDefinition(
    name="my_tool",
    description="Does something useful",
    input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    executor=my_tool,
))
```

Then import it in `main.py`: `import tools.my_tool`

### Add a new MCP server

```python
# In main.py startup:
from mcp.mcp_client import MCPClient, mcp_registry
mcp_registry.register("github", MCPClient("http://localhost:3002", "github"))
await mcp_registry.initialize_all()
```

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgements

- [Anthropic](https://anthropic.com) — Claude API
- [Tavily](https://tavily.com) — LLM-optimised search API
- [FastAPI](https://fastapi.tiangolo.com) — Python web framework
- [Model Context Protocol](https://modelcontextprotocol.io) — Tool interoperability standard
