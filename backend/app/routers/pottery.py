"""
API routes for Pottery
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from ..database import get_db
from ..models import Pottery
from ..schemas import PotteryResponse, PaginatedResponse

router = APIRouter(prefix="/pottery", tags=["Pottery"])


@router.get("/", response_model=List[PotteryResponse])
async def get_pottery_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    us: Optional[int] = None,
    tipo_reperto: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of pottery items"""
    query = db.query(Pottery)

    if sito:
        query = query.filter(Pottery.sito == sito)
    if area:
        query = query.filter(Pottery.area == area)
    if us is not None:
        query = query.filter(Pottery.us == us)
    if tipo_reperto:
        query = query.filter(Pottery.tipo_reperto == tipo_reperto)
    if search:
        query = query.filter(
            (Pottery.descrizione.ilike(f"%{search}%")) |
            (Pottery.definizione.ilike(f"%{search}%"))
        )

    pottery = query.order_by(
        Pottery.sito,
        Pottery.numero_inventario
    ).offset(skip).limit(limit).all()

    return pottery


@router.get("/paginated", response_model=PaginatedResponse)
async def get_pottery_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    us: Optional[int] = None,
    tipo_reperto: Optional[str] = None,
    datazione: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of pottery"""
    query = db.query(Pottery)

    if sito:
        query = query.filter(Pottery.sito == sito)
    if area:
        query = query.filter(Pottery.area == area)
    if us is not None:
        query = query.filter(Pottery.us == us)
    if tipo_reperto:
        query = query.filter(Pottery.tipo_reperto == tipo_reperto)
    if datazione:
        query = query.filter(Pottery.datazione.ilike(f"%{datazione}%"))
    if search:
        query = query.filter(
            (Pottery.descrizione.ilike(f"%{search}%")) |
            (Pottery.definizione.ilike(f"%{search}%"))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.order_by(
        Pottery.sito,
        Pottery.numero_inventario
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/types", response_model=List[str])
async def get_pottery_types(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of pottery types"""
    query = db.query(Pottery.tipo_reperto).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    types = query.all()
    return [t[0] for t in types if t[0]]


@router.get("/fabrics", response_model=List[str])
async def get_pottery_fabrics(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of ceramic fabrics (corpo ceramico)"""
    query = db.query(Pottery.corpo_ceramico).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    fabrics = query.all()
    return [f[0] for f in fabrics if f[0]]


@router.get("/statistics")
async def get_pottery_statistics(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get statistics about pottery"""
    query = db.query(Pottery)
    if sito:
        query = query.filter(Pottery.sito == sito)

    total = query.count()

    # Total weight
    total_weight = db.query(func.sum(Pottery.peso))
    if sito:
        total_weight = total_weight.filter(Pottery.sito == sito)
    total_weight = total_weight.scalar() or 0

    # Count by type
    by_type = db.query(
        Pottery.tipo_reperto,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_type = by_type.filter(Pottery.sito == sito)
    by_type = by_type.group_by(Pottery.tipo_reperto).all()

    # Count by fabric
    by_fabric = db.query(
        Pottery.corpo_ceramico,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_fabric = by_fabric.filter(Pottery.sito == sito)
    by_fabric = by_fabric.group_by(Pottery.corpo_ceramico).all()

    # Count by dating
    by_dating = db.query(
        Pottery.datazione,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_dating = by_dating.filter(Pottery.sito == sito)
    by_dating = by_dating.group_by(Pottery.datazione).all()

    return {
        "total": total,
        "total_weight_g": total_weight,
        "by_type": {t[0] or "N/A": t[1] for t in by_type},
        "by_fabric": {f[0] or "N/A": f[1] for f in by_fabric},
        "by_dating": {d[0] or "N/A": d[1] for d in by_dating}
    }


@router.get("/{pottery_id}", response_model=PotteryResponse)
async def get_pottery(pottery_id: int, db: Session = Depends(get_db)):
    """Get a specific pottery item by ID"""
    pottery = db.query(Pottery).filter(Pottery.id_rep == pottery_id).first()
    if not pottery:
        raise HTTPException(status_code=404, detail="Pottery not found")
    return pottery
