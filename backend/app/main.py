"""
PyArchInit Web Viewer - Main FastAPI Application
=================================================

A web application for viewing archaeological data from PyArchInit databases.
Supports viewing US, Materials, Pottery, Sites and associated media.

Features:
- REST API for archaeological data
- Media viewing via PyArchInit Storage Server integration
- Export to PDF and Excel
- Materials inventory summary (boxes, storage locations)

Author: PyArchInit Team
License: GPL v2
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
import os

from .config import settings
from .routers import (
    sites_router,
    us_router,
    materiali_router,
    pottery_router,
    media_router,
    export_router,
    auth_router
)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Web viewer for PyArchInit archaeological data",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Setup templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(sites_router, prefix="/api")
app.include_router(us_router, prefix="/api")
app.include_router(materiali_router, prefix="/api")
app.include_router(pottery_router, prefix="/api")
app.include_router(media_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


# Root endpoint - serve landing page
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Serve the landing/presentation page"""
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "app_name": settings.APP_NAME
    })


# Login page
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "app_name": settings.APP_NAME
    })


# Main app (protected)
@app.get("/app", response_class=HTMLResponse)
async def main_app(request: Request):
    """Serve the main web application"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "storage_server_url": settings.STORAGE_SERVER_URL
    })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {
        "message": "PyArchInit Web API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/sites", "description": "Archaeological sites"},
            {"path": "/api/us", "description": "Stratigraphic units"},
            {"path": "/api/materiali", "description": "Materials inventory"},
            {"path": "/api/pottery", "description": "Pottery records"},
            {"path": "/api/media", "description": "Media files"},
            {"path": "/api/export", "description": "Export to PDF/Excel"}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
