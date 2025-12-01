"""
API routes for Stratigraphic Units (US)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from ..database import get_db
from ..models import US
from ..schemas import USResponse, PaginatedResponse

router = APIRouter(prefix="/us", tags=["Stratigraphic Units"])


@router.get("/", response_model=List[USResponse])
async def get_us_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of stratigraphic units"""
    query = db.query(US)

    if sito:
        query = query.filter(US.sito == sito)
    if area:
        query = query.filter(US.area == area)
    if search:
        query = query.filter(
            (US.descrizione.ilike(f"%{search}%")) |
            (US.interpretazione.ilike(f"%{search}%")) |
            (US.d_stratigrafica.ilike(f"%{search}%"))
        )

    us_list = query.order_by(US.sito, US.area, US.us).offset(skip).limit(limit).all()
    return us_list


@router.get("/paginated", response_model=PaginatedResponse)
async def get_us_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    periodo: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of stratigraphic units"""
    query = db.query(US)

    if sito:
        query = query.filter(US.sito == sito)
    if area:
        query = query.filter(US.area == area)
    if periodo:
        query = query.filter(US.periodo_iniziale == periodo)
    if search:
        query = query.filter(
            (US.descrizione.ilike(f"%{search}%")) |
            (US.interpretazione.ilike(f"%{search}%"))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.order_by(US.sito, US.area, US.us).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/areas", response_model=List[str])
async def get_areas(sito: Optional[str] = None, db: Session = Depends(get_db)):
    """Get list of areas, optionally filtered by site"""
    query = db.query(US.area).distinct()
    if sito:
        query = query.filter(US.sito == sito)
    areas = query.all()
    return [a[0] for a in areas if a[0]]


@router.get("/periodi", response_model=List[str])
async def get_periodi(sito: Optional[str] = None, db: Session = Depends(get_db)):
    """Get list of periods"""
    query = db.query(US.periodo_iniziale).distinct()
    if sito:
        query = query.filter(US.sito == sito)
    periodi = query.all()
    return [p[0] for p in periodi if p[0]]


@router.get("/statistics")
async def get_us_statistics(sito: Optional[str] = None, db: Session = Depends(get_db)):
    """Get statistics about stratigraphic units"""
    query = db.query(US)
    if sito:
        query = query.filter(US.sito == sito)

    total = query.count()

    # Count by area
    by_area = db.query(
        US.area,
        func.count(US.id_us).label('count')
    )
    if sito:
        by_area = by_area.filter(US.sito == sito)
    by_area = by_area.group_by(US.area).all()

    # Count by period
    by_period = db.query(
        US.periodo_iniziale,
        func.count(US.id_us).label('count')
    )
    if sito:
        by_period = by_period.filter(US.sito == sito)
    by_period = by_period.group_by(US.periodo_iniziale).all()

    # Count by type
    by_type = db.query(
        US.d_stratigrafica,
        func.count(US.id_us).label('count')
    )
    if sito:
        by_type = by_type.filter(US.sito == sito)
    by_type = by_type.group_by(US.d_stratigrafica).all()

    return {
        "total": total,
        "by_area": {a[0] or "N/A": a[1] for a in by_area},
        "by_period": {p[0] or "N/A": p[1] for p in by_period},
        "by_type": {t[0] or "N/A": t[1] for t in by_type}
    }


@router.get("/{us_id}", response_model=USResponse)
async def get_us(us_id: int, db: Session = Depends(get_db)):
    """Get a specific stratigraphic unit by ID"""
    us = db.query(US).filter(US.id_us == us_id).first()
    if not us:
        raise HTTPException(status_code=404, detail="US not found")
    return us


@router.get("/by-number/{sito}/{area}/{us_number}", response_model=USResponse)
async def get_us_by_number(sito: str, area: str, us_number: int, db: Session = Depends(get_db)):
    """Get a specific US by site, area and US number"""
    us = db.query(US).filter(
        US.sito == sito,
        US.area == area,
        US.us == us_number
    ).first()
    if not us:
        raise HTTPException(status_code=404, detail="US not found")
    return us
