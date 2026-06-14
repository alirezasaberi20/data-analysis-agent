"""FastAPI application for the Data Analysis Agent."""

import asyncio
import io
import json
import traceback
from pathlib import Path
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from backend.config import CHART_OUTPUT_DIR
from backend.database import seed_database
from backend.database.connection import (
    get_table_info, load_dataframe_to_db, load_sql_file_to_db, drop_table,
)
from backend.vector_store.store import SchemaVectorStore
from backend.sessions.manager import SessionManager
from backend.agents.orchestrator import create_analysis_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database()
    vector_store = SchemaVectorStore()
    vector_store.index_schema()
    print("Database seeded and vector store indexed.")
    yield


app = FastAPI(
    title="Data Analysis Agent",
    description="Multi-agent data analysis system powered by LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

charts_dir = Path(CHART_OUTPUT_DIR)
charts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=str(charts_dir)), name="charts")

session_manager = SessionManager()
analysis_graph = create_analysis_graph()


# ---- Pydantic Models ----

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    charts: list[str]
    sql_results: list[str]
    steps: list[str]


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    created_at: float


# ---- REST Endpoints ----

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "data-analysis-agent"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = session_manager.get_or_create_session(request.session_id)
    session.add_message("user", request.message)

    history = session.get_history(max_messages=10)
    lang_messages = []
    for msg in history:
        if msg["role"] == "user":
            lang_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lang_messages.append(AIMessage(content=msg["content"]))

    initial_state = {
        "messages": lang_messages,
        "plan": "",
        "schema": "",
        "context": "",
        "target_tables": [],
        "sql_results": [],
        "analysis_results": "",
        "python_chart_paths": [],
        "chart_paths": [],
        "final_report": "",
    }

    try:
        result = await asyncio.to_thread(analysis_graph.invoke, initial_state)
    except Exception as e:
        error_msg = f"Analysis error: {str(e)}"
        session.add_message("assistant", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    final_report = result.get("final_report", "")
    chart_paths = result.get("chart_paths", [])
    sql_results = result.get("sql_results", [])

    chart_urls = []
    for path in chart_paths:
        filename = Path(path).name
        chart_urls.append(f"/charts/{filename}")
        session.add_artifact("chart", path, filename)

    session.add_message("assistant", final_report, {
        "charts": chart_urls,
        "sql_results": sql_results,
    })

    steps = []
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content[:200]
            steps.append(content)

    return ChatResponse(
        session_id=session.session_id,
        response=final_report,
        charts=chart_urls,
        sql_results=sql_results,
        steps=steps,
    )


# ---- Data Upload Endpoints ----

@app.get("/api/tables")
async def list_tables():
    """List all tables in the database with metadata."""
    try:
        tables = get_table_info()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Form(default=""),
):
    """Upload a CSV, Excel, or SQL file to the database.

    - CSV/Excel: loaded as a new table (table_name derived from filename if not given)
    - SQL: executed directly (CREATE TABLE + INSERT statements)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".csv", ".xlsx", ".xls", ".sql", ".tsv"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(allowed)}",
        )

    content = await file.read()

    try:
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(content))
            name = table_name or file.filename
            result = load_dataframe_to_db(df, name)
            msg = f"Loaded {result['rows']} rows into table '{result['table_name']}'"

        elif suffix == ".tsv":
            df = pd.read_csv(io.BytesIO(content), sep="\t")
            name = table_name or file.filename
            result = load_dataframe_to_db(df, name)
            msg = f"Loaded {result['rows']} rows into table '{result['table_name']}'"

        elif suffix in (".xlsx", ".xls"):
            xls = pd.ExcelFile(io.BytesIO(content))
            results = []
            for sheet in xls.sheet_names:
                df = xls.parse(sheet)
                if df.empty:
                    continue
                name = table_name if (table_name and len(xls.sheet_names) == 1) else sheet
                info = load_dataframe_to_db(df, name)
                results.append(info)
            msg = f"Loaded {len(results)} sheet(s): " + ", ".join(
                f"'{r['table_name']}' ({r['rows']} rows)" for r in results
            )
            result = results

        elif suffix == ".sql":
            sql_text = content.decode("utf-8")
            new_tables = load_sql_file_to_db(sql_text)
            result = {"new_tables": new_tables}
            msg = f"Executed SQL file. New tables: {', '.join(new_tables) or 'none (data inserted into existing tables)'}"

        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Re-index vector store so agents know about the new schema
        vector_store = SchemaVectorStore()
        vector_store.reindex_schema()

        tables = get_table_info()
        return {"message": msg, "result": result, "tables": tables}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@app.delete("/api/tables/{table_name}")
async def delete_table(table_name: str):
    """Remove a table from the database."""
    if drop_table(table_name):
        vector_store = SchemaVectorStore()
        vector_store.reindex_schema()
        return {"status": "deleted", "table": table_name}
    raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")


# ---- WebSocket for streaming ----

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session = session_manager.create_session()
    await websocket.send_json({
        "type": "session",
        "session_id": session.session_id,
    })

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            message = payload.get("message", "")

            if not message:
                continue

            session.add_message("user", message)

            # Stream step updates
            steps_map = {
                "planner": "Planning analysis...",
                "sql_agent": "Executing SQL queries...",
                "python_agent": "Running Python analysis...",
                "chart_agent": "Generating charts...",
                "insight_agent": "Synthesizing insights...",
            }

            history = session.get_history(max_messages=10)
            lang_messages = []
            for msg in history:
                if msg["role"] == "user":
                    lang_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lang_messages.append(AIMessage(content=msg["content"]))

            initial_state = {
                "messages": lang_messages,
                "plan": "",
                "schema": "",
                "context": "",
                "target_tables": [],
                "sql_results": [],
                "analysis_results": "",
                "python_chart_paths": [],
                "chart_paths": [],
                "final_report": "",
            }

            try:
                # Stream through graph nodes
                step_count = 0
                final_state = None

                def run_graph():
                    return analysis_graph.invoke(initial_state)

                # Send progress updates while processing
                async def send_progress():
                    node_names = list(steps_map.keys())
                    for i, node in enumerate(node_names):
                        await websocket.send_json({
                            "type": "step",
                            "step": steps_map[node],
                            "progress": int((i + 1) / len(node_names) * 100),
                        })
                        await asyncio.sleep(0.5)

                progress_task = asyncio.create_task(send_progress())
                result = await asyncio.to_thread(run_graph)
                await progress_task

                final_report = result.get("final_report", "")
                chart_paths = result.get("chart_paths", [])
                sql_results = result.get("sql_results", [])

                chart_urls = []
                for path in chart_paths:
                    filename = Path(path).name
                    chart_urls.append(f"/charts/{filename}")

                session.add_message("assistant", final_report, {
                    "charts": chart_urls,
                    "sql_results": sql_results,
                })

                await websocket.send_json({
                    "type": "response",
                    "response": final_report,
                    "charts": chart_urls,
                    "sql_results": sql_results,
                })

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

    except WebSocketDisconnect:
        session_manager.delete_session(session.session_id)


# ---- Session Management ----

@app.get("/api/sessions", response_model=list[SessionInfo])
async def list_sessions():
    sessions = []
    for sid in session_manager.list_sessions():
        s = session_manager.get_session(sid)
        if s:
            sessions.append(SessionInfo(
                session_id=s.session_id,
                message_count=len(s.messages),
                created_at=s.created_at,
            ))
    return sessions


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "messages": session.get_history(),
        "artifacts": session.artifacts,
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_manager.delete_session(session_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")
