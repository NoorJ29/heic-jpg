import os
import io
import uuid
import json
import shutil
import zipfile
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from heic_engine import convert_file, load_history, undo_last, save_history

app = FastAPI(title="HEIC -> JPG Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
CONVERSION_SESSIONS = BASE_DIR / "_sessions"

CONVERSION_SESSIONS.mkdir(exist_ok=True)

sessions: dict[str, dict] = {}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/convert")
async def convert_endpoint(
    files: List[UploadFile] = File(...),
    quality: int = Form(100),
):
    if not files:
        raise HTTPException(400, "No files provided")

    session_id = uuid.uuid4().hex[:12]
    session_dir = CONVERSION_SESSIONS / session_id
    session_dir.mkdir(parents=True)

    results = []
    conversions_log = []

    for f in files:
        stem = Path(f.filename).stem
        orig_bytes = await f.read()
        orig_size = len(orig_bytes)

        src_path = session_dir / f.filename
        src_path.write_bytes(orig_bytes)

        out_name = f"{stem}.jpg"
        out_path = session_dir / out_name

        try:
            conv_result = convert_file(src_path, out_path, quality=quality)
            jpg_bytes = out_path.read_bytes()
            jpg_size = len(jpg_bytes)
            pct = (1 - jpg_size / orig_size) * 100 if orig_size else 0

            results.append({
                "name": out_name,
                "size": jpg_size,
                "original": orig_size,
                "savings": round(pct, 1),
            })
            conversions_log.append({
                "source": f.filename,
                "target": out_name,
                "source_size": orig_size,
                "target_size": jpg_size,
            })
        except Exception as e:
            results.append({
                "name": out_name,
                "size": 0,
                "original": orig_size,
                "savings": 0,
                "error": str(e),
            })

        src_path.unlink(missing_ok=True)

    sessions[session_id] = {
        "dir": str(session_dir),
        "results": results,
        "created": datetime.now().isoformat(),
    }

    if conversions_log:
        save_history({
            "timestamp": datetime.now().isoformat(),
            "conversions": conversions_log,
            "quality": quality,
        })

    total_orig = sum(r["original"] for r in results if "error" not in r)
    total_new = sum(r["size"] for r in results if "error" not in r)
    total_pct = (1 - total_new / max(total_orig, 1)) * 100

    return {
        "session_id": session_id,
        "results": results,
        "total": {
            "files": len(results),
            "original": total_orig,
            "converted": total_new,
            "savings": round(total_pct, 1),
        },
        "quality": quality,
    }


@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    file_path = Path(session["dir"]) / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")

    return FileResponse(
        str(file_path),
        media_type="image/jpeg",
        filename=filename,
    )


@app.get("/api/download/{session_id}/zip")
async def download_zip(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in session["results"]:
            fp = Path(session["dir"]) / r["name"]
            if fp.exists():
                zf.writestr(r["name"], fp.read_bytes())
    zip_buf.seek(0)

    return StreamingResponse(
        iter([zip_buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=converted-{session_id}.zip"},
    )


@app.get("/api/history")
async def get_history():
    return {"history": load_history()}


@app.post("/api/history/undo")
async def undo():
    ok, msg = undo_last()
    return {"ok": ok, "message": msg}


@app.post("/api/history/clear")
async def clear_history():
    path = Path.home() / ".heic_renamer_history.json"
    path.write_text("[]")
    return {"ok": True}


@app.on_event("startup")
async def cleanup_old_sessions():
    for d in CONVERSION_SESSIONS.iterdir():
        if d.is_dir():
            age = datetime.now().timestamp() - d.stat().st_mtime
            if age > 3600:
                shutil.rmtree(d, ignore_errors=True)


@app.on_event("startup")
async def ensure_dirs():
    STATIC_DIR.mkdir(exist_ok=True)
    TEMPLATES_DIR.mkdir(exist_ok=True)
