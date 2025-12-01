"""
API routes for archaeological sites
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from ..database import get_db
from ..models import Site
from ..schemas import SiteResponse, PaginatedResponse

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get("/", response_model=List[SiteResponse])
async def get_sites(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all archaeological sites"""
    query = db.query(Site)

    if search:
        query = query.filter(Site.sito.ilike(f"%{search}%"))

    sites = query.offset(skip).limit(limit).all()
    return sites


@router.get("/paginated", response_model=PaginatedResponse)
async def get_sites_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of sites"""
    query = db.query(Site)

    if search:
        query = query.filter(Site.sito.ilike(f"%{search}%"))

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/names", response_model=List[str])
async def get_site_names(db: Session = Depends(get_db)):
    """Get list of all site names"""
    sites = db.query(Site.sito).distinct().all()
    return [s[0] for s in sites if s[0]]


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """Get a specific site by ID"""
    site = db.query(Site).filter(Site.id_sito == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/by-name/{site_name}", response_model=SiteResponse)
async def get_site_by_name(site_name: str, db: Session = Depends(get_db)):
    """Get a specific site by name"""
    site = db.query(Site).filter(Site.sito == site_name).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
