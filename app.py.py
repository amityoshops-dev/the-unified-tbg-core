from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import pathlib

app = FastAPI(title="YES Bank TBG-Core Enterprise Platform", version="2026.4.1")

# Mount static web assets
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_root_dashboard():
    return FileResponse("static/index.html")

@app.get("/api/v1/system/docs/prd", response_class=HTMLResponse)
async def get_system_prd():
    """Serves the raw Part 1 PRD and Mermaid diagrams to the frontend viewer"""
    prd_path = pathlib.Path("docs/PRD_ARCHITECTURE.md")
    if prd_path.exists():
        return prd_path.read_text(encoding="utf-8")
    return "# PRD Not Found"