"""
API routes for Stratigraphic Units (US)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, exists, and_
from typing import List, Optional

from ..database import get_db
from ..models import US, USView
from ..schemas import USResponse, PaginatedResponse

router = APIRouter(prefix="/us", tags=["Stratigraphic Units"])


def add_geometry_info(us_list: List, db: Session) -> List[dict]:
    """Add has_geometry field to US list by checking the view"""
    if not us_list:
        return []

    # Get all US IDs that have geometry from the view
    us_with_geom = db.query(USView.id_us).filter(USView.the_geom.isnot(None)).all()
    us_ids_with_geom = {row[0] for row in us_with_geom}

    # Convert to dicts with has_geometry field
    result = []
    for us in us_list:
        us_dict = {
            "id_us": us.id_us,
            "sito": us.sito,
            "area": us.area,
            "us": us.us,
            "d_stratigrafica": us.d_stratigrafica,
            "d_interpretativa": us.d_interpretativa,
            "descrizione": us.descrizione,
            "interpretazione": us.interpretazione,
            "periodo_iniziale": us.periodo_iniziale,
            "fase_iniziale": us.fase_iniziale,
            "periodo_finale": us.periodo_finale,
            "fase_finale": us.fase_finale,
            "datazione": us.datazione,
            "anno_scavo": us.anno_scavo,
            "scavato": us.scavato,
            "order_layer": us.order_layer,
            "unita_tipo": us.unita_tipo,
            "settore": us.settore,
            "quota_min_abs": float(us.quota_min_abs) if us.quota_min_abs else None,
            "quota_max_abs": float(us.quota_max_abs) if us.quota_max_abs else None,
            "has_geometry": us.id_us in us_ids_with_geom
        }
        result.append(us_dict)
    return result


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
    return add_geometry_info(us_list, db)


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
    items_with_geom = add_geometry_info(items, db)

    return {
        "items": items_with_geom,
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

    # Count with geometry
    with_geometry = db.query(func.count(USView.id_us)).filter(USView.the_geom.isnot(None))
    if sito:
        with_geometry = with_geometry.filter(USView.sito == sito)
    with_geometry = with_geometry.scalar() or 0

    return {
        "total": total,
        "with_geometry": with_geometry,
        "without_geometry": total - with_geometry,
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
    result = add_geometry_info([us], db)
    return result[0] if result else us


@router.get("/by-number/{sito}/{area}/{us_number}", response_model=USResponse)
async def get_us_by_number(sito: str, area: str, us_number: str, db: Session = Depends(get_db)):
    """Get a specific US by site, area and US number"""
    us = db.query(US).filter(
        US.sito == sito,
        US.area == area,
        US.us == us_number
    ).first()
    if not us:
        raise HTTPException(status_code=404, detail="US not found")
    result = add_geometry_info([us], db)
    return result[0] if result else us
