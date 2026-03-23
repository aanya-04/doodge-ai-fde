"""
main.py - FastAPI application
All API routes for the graph system.
"""

import os
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from database import init_db, load_excel_dataset, get_schema_info, get_tables, execute_query, DB_PATH
from graph import build_graph, get_graph_for_vis, get_node_neighbors, get_graph_summary
from llm import get_engine

# ── APP SETUP ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Graph Data System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent.parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── STARTUP ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    # If DB already has data, build graph immediately
    tables = get_tables()
    if tables and any(t in tables for t in ["sales_orders", "deliveries", "billing_documents"]):
        try:
            build_graph()
            print("✅ Graph loaded from existing DB on startup")
        except Exception as e:
            print(f"⚠️ Could not pre-build graph: {e}")


# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "db_exists": DB_PATH.exists()}


# ── DATASET UPLOAD ────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and ingest the Excel dataset."""
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Only .xlsx, .xls, or .csv files are accepted.")

    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        init_db()
        load_excel_dataset(str(dest))
        build_graph()
        get_engine().invalidate_cache()
        tables = get_tables()
        summary = get_graph_summary()
        return {
            "success": True,
            "message": f"Dataset loaded successfully.",
            "tables": tables,
            "graph_summary": summary
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to load dataset: {str(e)}")


# ── GRAPH ─────────────────────────────────────────────────────────────────────

@app.get("/graph")
def graph_data(limit: int = 300):
    """Return graph data for Cytoscape.js visualization."""
    try:
        data = get_graph_for_vis(limit_nodes=limit)
        return data
    except Exception as e:
        raise HTTPException(500, f"Graph error: {str(e)}")


@app.get("/graph/summary")
def graph_summary():
    """Return graph statistics."""
    try:
        return get_graph_summary()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/graph/node/{node_id:path}")
def node_neighbors(node_id: str):
    """Expand a node and return its neighbors."""
    try:
        return get_node_neighbors(node_id)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── QUERY ─────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    conversation_history: Optional[List[dict]] = []


@app.post("/query")
def query(req: QueryRequest):
    """Main NL query endpoint."""
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")
    if len(req.question) > 500:
        raise HTTPException(400, "Question too long (max 500 characters).")

    engine = get_engine()
    result = engine.query(req.question, req.conversation_history)
    return result


# ── SCHEMA ────────────────────────────────────────────────────────────────────

@app.get("/schema")
def schema():
    """Return database schema info."""
    tables = get_tables()
    schema_info = {}
    for table in tables:
        rows, _ = execute_query(f"SELECT COUNT(*) as cnt FROM {table}")
        count = rows[0]["cnt"] if rows else 0
        cols_rows, _ = execute_query(f"PRAGMA table_info({table})")
        cols = [r["name"] for r in (cols_rows or [])]
        schema_info[table] = {"columns": cols, "row_count": count}
    return schema_info


# ── EXAMPLE QUERIES ───────────────────────────────────────────────────────────

@app.get("/examples")
def example_queries():
    return {
        "examples": [
            "Which products are associated with the highest number of billing documents?",
            "Trace the full flow of billing document B1001 (Sales Order → Delivery → Billing → Journal Entry)",
            "Identify sales orders that have been delivered but not billed",
            "Which customers have the highest total order value?",
            "Show me all deliveries to a specific plant",
            "Which billing documents have no associated payments?",
            "What is the total revenue per customer?",
            "Show me sales orders with missing deliveries",
        ]
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
