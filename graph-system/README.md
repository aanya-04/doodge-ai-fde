# GraphIQ — Business Data Intelligence System

A graph-based data modeling and NL query system for exploring business data (orders, deliveries, billing, payments) through an interactive graph visualization and conversational AI interface.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                │
│  ┌──────────────────┐  ┌──────────────────────┐ │
│  │  Graph Viewer    │  │   Chat / Query Panel  │ │
│  │  (Cytoscape.js)  │  │   (NL → SQL → NL)    │ │
│  └──────────────────┘  └──────────────────────┘ │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────┐
│                Backend (FastAPI)                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ database │  │  graph   │  │     llm       │ │
│  │ SQLite   │  │ NetworkX │  │ Gemini Flash  │ │
│  └──────────┘  └──────────┘  └───────────────┘ │
└─────────────────────────────────────────────────┘
```

### Key Design Decisions

**Database: SQLite**
- Zero-config, file-based — no infrastructure needed
- Full SQL support for complex joins across orders/deliveries/billing
- Schema mirrors the business domain (normalized relational model)
- Tradeoff: not suitable for TB-scale, but perfect for this dataset

**Graph Layer: NetworkX (in-memory)**
- Built on top of SQLite data at startup
- Directed graph (DiGraph) with typed nodes and labeled edges
- Enables path traversal and neighbor expansion that SQL can't express cleanly
- Tradeoff: rebuilt on every server restart (acceptable given dataset size)

**LLM: Google Gemini 1.5 Flash (free tier)**
- Two-stage pipeline: (1) NL → SQL, (2) SQL results → NL answer
- System prompt includes full DB schema and strict guardrails
- Returns structured JSON from Stage 1 to safely parse SQL

**Graph Visualization: Cytoscape.js**
- Force-directed layout (Cola.js) for organic graph rendering
- Node size scales with degree centrality
- Type-based colors and shapes for visual hierarchy
- Double-click to expand neighbors, click for metadata panel

---

## LLM Prompting Strategy

### Stage 1 — Query Classification + SQL Generation

The system prompt:
1. Lists all tables + columns + sample rows from the live DB
2. Explicitly forbids non-dataset questions and defines the guardrail response format
3. Requires JSON-only output (`{"guardrail": bool, "sql": "...", "explanation": "..."}`)
4. Instructs the model to only use tables/columns that exist

This prevents hallucinated table names and forces structured output that can be safely parsed.

### Stage 2 — Natural Language Answer

A second prompt takes the raw SQL results + original question and asks the model to write a concise, data-backed answer. This decouples "query generation" from "answer writing", making each step more reliable.

---

## Guardrails

The system refuses off-topic questions in two layers:

1. **LLM-level**: The system prompt instructs Gemini to return `{"guardrail": true, "message": "..."}` for non-dataset questions
2. **Backend-level**: Input is validated (length, empty check) before reaching the LLM
3. **SQL safety**: Only `SELECT` queries are executed — no DML/DDL allowed. The execute function wraps in try/catch and returns errors safely.

Example rejected prompts:
- "What is the capital of France?" → guardrail
- "Write me a poem" → guardrail
- "What is 2+2?" → guardrail
- "Show me orders" → valid ✓

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Gemini API key (free at https://ai.google.dev)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

python main.py
# Server starts at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm start
# App opens at http://localhost:3000
```

### Load the Dataset

1. Open http://localhost:3000
2. Click **Upload Dataset** (top right)
3. Select your `.xlsx` file
4. The graph builds automatically

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/upload` | Upload Excel dataset |
| GET | `/graph` | Get graph data for visualization |
| GET | `/graph/summary` | Node/edge counts by type |
| GET | `/graph/node/{id}` | Expand node neighbors |
| POST | `/query` | NL query → SQL → NL answer |
| GET | `/schema` | Database schema info |
| GET | `/examples` | Sample queries |

---

## Example Queries

- "Which products are associated with the highest number of billing documents?"
- "Trace the full flow of billing document B1001"
- "Show me sales orders that have been delivered but not billed"
- "Which customers have the highest total order value?"
- "Find all billing documents with no associated payments"
- "What is the total revenue per product?"
- "Show deliveries by plant"

---

## File Structure

```
graph-system/
├── backend/
│   ├── main.py          # FastAPI routes
│   ├── database.py      # SQLite setup + data ingestion
│   ├── graph.py         # NetworkX graph construction
│   ├── llm.py           # Gemini integration + query pipeline
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Root component + layout
│   │   ├── App.css              # All styles
│   │   └── components/
│   │       ├── GraphViewer.jsx  # Cytoscape graph
│   │       ├── ChatPanel.jsx    # NL query interface
│   │       ├── UploadPanel.jsx  # Dataset upload
│   │       └── StatsBar.jsx     # Graph statistics
│   ├── public/index.html
│   └── package.json
├── data/                # Created at runtime
│   ├── graph.db         # SQLite database
│   └── uploads/         # Uploaded files
└── README.md
```
