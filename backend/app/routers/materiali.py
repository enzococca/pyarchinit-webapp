"""
API routes for Materials Inventory
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List, Optional
from collections import defaultdict

from ..database import get_db
from ..models import InventarioMateriali
from ..schemas import MaterialeResponse, PaginatedResponse, MaterialsSummary, StorageSummary, BoxSummary

router = APIRouter(prefix="/materiali", tags=["Materials Inventory"])


@router.get("/", response_model=List[MaterialeResponse])
async def get_materiali(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    us: Optional[str] = None,
    nr_cassa: Optional[int] = None,
    luogo_conservazione: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of materials"""
    query = db.query(InventarioMateriali)

    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    if area:
        query = query.filter(InventarioMateriali.area == area)
    if us is not None:
        query = query.filter(InventarioMateriali.us == us)
    if nr_cassa:
        query = query.filter(InventarioMateriali.nr_cassa == nr_cassa)
    if luogo_conservazione:
        query = query.filter(InventarioMateriali.luogo_conservazione == luogo_conservazione)
    if tipo_reperto:
        query = query.filter(InventarioMateriali.tipo_reperto == tipo_reperto)
    if search:
        query = query.filter(
            (InventarioMateriali.descrizione.ilike(f"%{search}%")) |
            (InventarioMateriali.definizione.ilike(f"%{search}%"))
        )

    materiali = query.order_by(
        InventarioMateriali.sito,
        InventarioMateriali.numero_inventario
    ).offset(skip).limit(limit).all()

    return materiali


@router.get("/paginated", response_model=PaginatedResponse)
async def get_materiali_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sito: Optional[str] = None,
    area: Optional[str] = None,
    us: Optional[str] = None,
    nr_cassa: Optional[int] = None,
    luogo_conservazione: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of materials"""
    query = db.query(InventarioMateriali)

    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    if area:
        query = query.filter(InventarioMateriali.area == area)
    if us is not None:
        query = query.filter(InventarioMateriali.us == us)
    if nr_cassa:
        query = query.filter(InventarioMateriali.nr_cassa == nr_cassa)
    if luogo_conservazione:
        query = query.filter(InventarioMateriali.luogo_conservazione == luogo_conservazione)
    if tipo_reperto:
        query = query.filter(InventarioMateriali.tipo_reperto == tipo_reperto)
    if search:
        query = query.filter(
            (InventarioMateriali.descrizione.ilike(f"%{search}%")) |
            (InventarioMateriali.definizione.ilike(f"%{search}%"))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    items = query.order_by(
        InventarioMateriali.sito,
        InventarioMateriali.numero_inventario
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/summary", response_model=MaterialsSummary)
async def get_materials_summary(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive summary of materials inventory.
    Includes breakdown by storage location, boxes, and material types.
    """
    query = db.query(InventarioMateriali)
    if sito:
        query = query.filter(InventarioMateriali.sito == sito)

    all_materials = query.all()

    # Total count
    total_materials = len(all_materials)

    # Group by storage location
    storage_data = defaultdict(lambda: {"boxes": defaultdict(lambda: {"items": [], "types": set()})})

    for mat in all_materials:
        storage = mat.luogo_conservazione or "Non specificato"
        box = mat.nr_cassa or "Non specificata"
        storage_data[storage]["boxes"][box]["items"].append(mat)
        if mat.tipo_reperto:
            storage_data[storage]["boxes"][box]["types"].add(mat.tipo_reperto)

    # Build storage summaries
    storage_locations = []
    total_boxes = 0

    for storage_name, storage_info in storage_data.items():
        boxes = []
        for box_name, box_info in storage_info["boxes"].items():
            boxes.append(BoxSummary(
                nr_cassa=box_name if box_name != "Non specificata" else 0,
                luogo_conservazione=storage_name,
                total_items=len(box_info["items"]),
                types=list(box_info["types"])
            ))
            total_boxes += 1

        storage_locations.append(StorageSummary(
            luogo_conservazione=storage_name,
            total_boxes=len(boxes),
            total_items=sum(b.total_items for b in boxes),
            boxes=sorted(boxes, key=lambda x: x.nr_cassa if isinstance(x.nr_cassa, int) else 0)
        ))

    # Count by type
    by_type = defaultdict(int)
    for mat in all_materials:
        tipo = mat.tipo_reperto or "Non specificato"
        by_type[tipo] += 1

    # Count by site
    by_site = defaultdict(int)
    for mat in all_materials:
        site = mat.sito or "Non specificato"
        by_site[site] += 1

    return MaterialsSummary(
        total_materials=total_materials,
        total_boxes=total_boxes,
        storage_locations=sorted(storage_locations, key=lambda x: x.luogo_conservazione),
        by_type=dict(by_type),
        by_site=dict(by_site)
    )


@router.get("/boxes", response_model=List[BoxSummary])
async def get_boxes(
    sito: Optional[str] = None,
    luogo_conservazione: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of boxes with item counts"""
    query = db.query(
        InventarioMateriali.nr_cassa,
        InventarioMateriali.luogo_conservazione,
        func.count(InventarioMateriali.id_invmat).label('count')
    )

    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    if luogo_conservazione:
        query = query.filter(InventarioMateriali.luogo_conservazione == luogo_conservazione)

    results = query.group_by(
        InventarioMateriali.nr_cassa,
        InventarioMateriali.luogo_conservazione
    ).all()

    boxes = []
    for r in results:
        if r[0]:  # Skip null box numbers
            # Get types in this box
            types_query = db.query(distinct(InventarioMateriali.tipo_reperto)).filter(
                InventarioMateriali.nr_cassa == r[0]
            )
            if sito:
                types_query = types_query.filter(InventarioMateriali.sito == sito)
            types = [t[0] for t in types_query.all() if t[0]]

            boxes.append(BoxSummary(
                nr_cassa=r[0],
                luogo_conservazione=r[1],
                total_items=r[2],
                types=types
            ))

    return sorted(boxes, key=lambda x: x.nr_cassa if isinstance(x.nr_cassa, int) else 0)


@router.get("/storage-locations", response_model=List[str])
async def get_storage_locations(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of storage locations"""
    query = db.query(distinct(InventarioMateriali.luogo_conservazione))
    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    locations = query.all()
    return [loc[0] for loc in locations if loc[0]]


@router.get("/types", response_model=List[str])
async def get_material_types(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of material types"""
    query = db.query(distinct(InventarioMateriali.tipo_reperto))
    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    types = query.all()
    return [t[0] for t in types if t[0]]


@router.get("/statistics")
async def get_materials_statistics(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get statistics about materials"""
    query = db.query(InventarioMateriali)
    if sito:
        query = query.filter(InventarioMateriali.sito == sito)

    total = query.count()

    # Total weight
    total_weight = db.query(func.sum(InventarioMateriali.peso))
    if sito:
        total_weight = total_weight.filter(InventarioMateriali.sito == sito)
    total_weight = total_weight.scalar() or 0

    # Total fragments
    total_fragments = db.query(func.sum(InventarioMateriali.totale_frammenti))
    if sito:
        total_fragments = total_fragments.filter(InventarioMateriali.sito == sito)
    total_fragments = total_fragments.scalar() or 0

    # Count by type
    by_type = db.query(
        InventarioMateriali.tipo_reperto,
        func.count(InventarioMateriali.id_invmat).label('count')
    )
    if sito:
        by_type = by_type.filter(InventarioMateriali.sito == sito)
    by_type = by_type.group_by(InventarioMateriali.tipo_reperto).all()

    # Count by storage
    by_storage = db.query(
        InventarioMateriali.luogo_conservazione,
        func.count(InventarioMateriali.id_invmat).label('count')
    )
    if sito:
        by_storage = by_storage.filter(InventarioMateriali.sito == sito)
    by_storage = by_storage.group_by(InventarioMateriali.luogo_conservazione).all()

    return {
        "total": total,
        "total_weight_kg": round(total_weight / 1000, 2) if total_weight else 0,
        "total_fragments": total_fragments,
        "by_type": {t[0] or "N/A": t[1] for t in by_type},
        "by_storage": {s[0] or "N/A": s[1] for s in by_storage}
    }


@router.get("/{materiale_id}", response_model=MaterialeResponse)
async def get_materiale(materiale_id: int, db: Session = Depends(get_db)):
    """Get a specific material by ID"""
    materiale = db.query(InventarioMateriali).filter(
        InventarioMateriali.id_invmat == materiale_id
    ).first()
    if not materiale:
        raise HTTPException(status_code=404, detail="Material not found")
    return materiale
