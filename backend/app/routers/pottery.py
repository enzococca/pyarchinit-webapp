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
    us: Optional[str] = None,
    form: Optional[str] = None,
    material: Optional[str] = None,
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
    if form:
        query = query.filter(Pottery.form == form)
    if material:
        query = query.filter(Pottery.material == material)
    if search:
        query = query.filter(
            (Pottery.note.ilike(f"%{search}%")) |
            (Pottery.form.ilike(f"%{search}%")) |
            (Pottery.specific_form.ilike(f"%{search}%"))
        )

    pottery = query.order_by(
        Pottery.sito,
        Pottery.id_number
    ).offset(skip).limit(limit).all()

    return pottery


@router.get("/paginated", response_model=PaginatedResponse)
async def get_pottery_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    us: Optional[str] = None,
    form: Optional[str] = None,
    material: Optional[str] = None,
    ware: Optional[str] = None,
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
    if form:
        query = query.filter(Pottery.form == form)
    if material:
        query = query.filter(Pottery.material == material)
    if ware:
        query = query.filter(Pottery.ware.ilike(f"%{ware}%"))
    if search:
        query = query.filter(
            (Pottery.note.ilike(f"%{search}%")) |
            (Pottery.form.ilike(f"%{search}%")) |
            (Pottery.specific_form.ilike(f"%{search}%"))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.order_by(
        Pottery.sito,
        Pottery.id_number
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/forms", response_model=List[str])
async def get_pottery_forms(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of pottery forms"""
    query = db.query(Pottery.form).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    forms = query.all()
    return [f[0] for f in forms if f[0]]


@router.get("/materials", response_model=List[str])
async def get_pottery_materials(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of pottery materials"""
    query = db.query(Pottery.material).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    materials = query.all()
    return [m[0] for m in materials if m[0]]


@router.get("/fabrics", response_model=List[str])
async def get_pottery_fabrics(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of ceramic fabrics"""
    query = db.query(Pottery.fabric).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    fabrics = query.all()
    return [f[0] for f in fabrics if f[0]]


@router.get("/wares", response_model=List[str])
async def get_pottery_wares(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of pottery wares"""
    query = db.query(Pottery.ware).distinct()
    if sito:
        query = query.filter(Pottery.sito == sito)
    wares = query.all()
    return [w[0] for w in wares if w[0]]


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

    # Total quantity
    total_qty = db.query(func.sum(Pottery.qty))
    if sito:
        total_qty = total_qty.filter(Pottery.sito == sito)
    total_qty = total_qty.scalar() or 0

    # Count by form
    by_form = db.query(
        Pottery.form,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_form = by_form.filter(Pottery.sito == sito)
    by_form = by_form.group_by(Pottery.form).all()

    # Count by material
    by_material = db.query(
        Pottery.material,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_material = by_material.filter(Pottery.sito == sito)
    by_material = by_material.group_by(Pottery.material).all()

    # Count by fabric
    by_fabric = db.query(
        Pottery.fabric,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_fabric = by_fabric.filter(Pottery.sito == sito)
    by_fabric = by_fabric.group_by(Pottery.fabric).all()

    # Count by ware
    by_ware = db.query(
        Pottery.ware,
        func.count(Pottery.id_rep).label('count')
    )
    if sito:
        by_ware = by_ware.filter(Pottery.sito == sito)
    by_ware = by_ware.group_by(Pottery.ware).all()

    return {
        "total": total,
        "total_qty": total_qty,
        "by_form": {f[0] or "N/A": f[1] for f in by_form},
        "by_material": {m[0] or "N/A": m[1] for m in by_material},
        "by_fabric": {f[0] or "N/A": f[1] for f in by_fabric},
        "by_ware": {w[0] or "N/A": w[1] for w in by_ware}
    }


@router.get("/{pottery_id}", response_model=PotteryResponse)
async def get_pottery(pottery_id: int, db: Session = Depends(get_db)):
    """Get a specific pottery item by ID"""
    pottery = db.query(Pottery).filter(Pottery.id_rep == pottery_id).first()
    if not pottery:
        raise HTTPException(status_code=404, detail="Pottery not found")
    return pottery
