"""FastAPI web server for the Multi-Agent Investment Committee UI."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DEFAULT_MODELS, DEFAULT_PROVIDER, PRICING, default_model_for
from providers import get_provider
from usage import UsageTracker

app = FastAPI(title="Investment Committee Terminal")

# CORS middleware for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

# In-memory jobs tracking for live committee runs
JOBS: dict[str, dict[str, Any]] = {}


class RunRequest(BaseModel):
    symbol: str
    provider: str | None = None
    model: str | None = None
    portfolio_context: str | None = None
    dry_run: bool = False


@app.get("/api/config")
async def get_system_config():
    """Return provider configuration, key status, and available models."""
    has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    gemini_models = [m for m in PRICING.keys() if m.startswith("gemini")]
    anthropic_models = [m for m in PRICING.keys() if m.startswith("claude")]

    return {
        "default_provider": DEFAULT_PROVIDER,
        "providers": {
            "gemini": {
                "name": "Google Gemini",
                "default_model": default_model_for("gemini"),
                "models": gemini_models,
                "has_key": has_gemini,
                "key_env_var": "GEMINI_API_KEY",
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "default_model": default_model_for("anthropic"),
                "models": anthropic_models,
                "has_key": has_anthropic,
                "key_env_var": "ANTHROPIC_API_KEY",
            },
        },
    }


@app.get("/api/analyses")
async def list_analyses():
    """List all completed committee transcripts with executive summary metadata."""
    files = list(TRANSCRIPTS_DIR.glob("*.json"))
    analyses = []

    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            
            memo = data.get("rounds", {}).get("final_chair_memo", {}).get("output", {})
            usage = data.get("usage", {})

            analyses.append({
                "id": f.name,
                "symbol": data.get("symbol", f.stem.split("_")[0]),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "decision": memo.get("decision", "HOLD").upper(),
                "confidence": memo.get("confidence", 0),
                "executive_summary": memo.get("executive_summary", ""),
                "vote_tally": data.get("vote_tally", {}),
                "total_cost_usd": usage.get("total_cost_usd", 0.0),
                "total_calls": usage.get("total_calls", 0),
                "total_tokens": usage.get("total_input_tokens", 0) + usage.get("total_output_tokens", 0),
            })
        except Exception:
            continue

    return {"analyses": analyses}


@app.get("/api/analyses/{filename}")
async def get_analysis_detail(filename: str):
    """Retrieve complete transcript JSON for a specific run."""
    safe_name = Path(filename).name
    file_path = TRANSCRIPTS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Analysis report not found")

    with open(file_path, "r", encoding="utf-8") as fp:
        return json.load(fp)


async def execute_committee_job(job_id: str, req: RunRequest):
    """Asynchronously execute a committee run and stream progress messages."""
    job = JOBS[job_id]
    q: asyncio.Queue = job["queue"]

    try:
        symbol = req.symbol.strip().upper()
        provider_name = (req.provider or DEFAULT_PROVIDER).lower()
        model = req.model or default_model_for(provider_name)
        portfolio_context = req.portfolio_context or "No specific portfolio context provided; assume a diversified retail portfolio."

        await q.put({"type": "stage", "stage": "init", "message": f"Initializing committee run for {symbol} with {provider_name.title()} ({model})..."})

        if req.dry_run:
            await q.put({"type": "stage", "stage": "info", "message": "Using dry-run simulation mode (mock LLM with live Yahoo Finance market tools)..."})
            import tests.mock_client as mc
            from tests.mock_client import FakeAsyncAnthropic
            from providers.anthropic_provider import AnthropicProvider
            fake_client = FakeAsyncAnthropic()
            provider = AnthropicProvider(client=fake_client)
        else:
            provider = get_provider(provider_name)
            valid, warn = provider.validate_credentials()
            if not valid:
                raise ValueError(warn)

        import committee

        tracker = UsageTracker()
        started_at = datetime.now(timezone.utc).isoformat()

        # Round 1
        await q.put({"type": "stage", "stage": "round1", "message": f"[1/4] Round 1: Running Fundamental, Technical, and Sentiment analysts in parallel for {symbol}..."})
        round1 = await committee.run_round1(provider, symbol, tracker, model, 8000)

        # Round 2
        await q.put({"type": "stage", "stage": "round2", "message": f"[2/4] Round 2: Running Risk Manager and Devil's Advocate in parallel..."})
        round2 = await committee.run_round2(provider, symbol, round1, portfolio_context, tracker, model, 8000)

        # Round 3
        await q.put({"type": "stage", "stage": "round3", "message": f"[3/4] Round 3: Processing Analyst rebuttals against Risk & Devil's Advocate critiques..."})
        round3 = await committee.run_round3(provider, symbol, round1, *round2, tracker, model, 8000)

        # Final Memo
        await q.put({"type": "stage", "stage": "final", "message": f"[4/4] Final: Committee Chair synthesizing debates into Investment Decision Memo..."})
        chair_result = await committee.run_chair(provider, symbol, round1, round2, round3, tracker, model, 8000)

        # Build & save transcript
        tally = committee.tally_votes(round3, *round2)
        transcript = committee.build_transcript(symbol, round1, round2, round3, chair_result, tracker, started_at)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_filename = f"{symbol}_{ts}.json"
        out_path = TRANSCRIPTS_DIR / out_filename
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(transcript, fp, indent=2, default=str)

        await q.put({
            "type": "complete",
            "filename": out_filename,
            "symbol": symbol,
            "decision": chair_result.parsed.get("decision", "HOLD").upper(),
            "confidence": chair_result.parsed.get("confidence", 0),
            "vote_tally": tally,
            "transcript": transcript,
        })
    except Exception as e:
        await q.put({"type": "error", "error": str(e)})
    finally:
        await q.put(None)  # Sentinel to end stream


@app.post("/api/run")
async def start_committee_run(req: RunRequest):
    """Trigger an investment committee deliberation."""
    if not req.symbol or not req.symbol.strip():
        raise HTTPException(status_code=400, detail="Ticker symbol is required")

    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    JOBS[job_id] = {
        "queue": queue,
        "symbol": req.symbol.strip().upper(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    asyncio.create_task(execute_committee_job(job_id, req))
    return {"job_id": job_id, "status": "started"}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """SSE endpoint streaming live updates of a committee deliberation."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    q: asyncio.Queue = JOBS[job_id]["queue"]

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            item = await q.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Investment Committee UI loading...</h1>", status_code=200)
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description="Start Investment Committee Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    print(f"\n==================================================================")
    print(f"  Investment Committee Terminal running at: http://{args.host}:{args.port}")
    print(f"==================================================================\n")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
