"""
API routes for exporting data to PDF and Excel
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from ..database import get_db
from ..models import US, InventarioMateriali, Pottery, Site

router = APIRouter(prefix="/export", tags=["Export"])


def create_excel_workbook(data: list, columns: list, title: str) -> io.BytesIO:
    """Create an Excel workbook from data"""
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel sheet name limit

    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Write headers
    for col_idx, column in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=column['label'])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Write data
    for row_idx, row_data in enumerate(data, 2):
        for col_idx, column in enumerate(columns, 1):
            value = getattr(row_data, column['field'], None)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(wrap_text=True)

    # Auto-adjust column widths
    for col_idx, column in enumerate(columns, 1):
        max_length = len(str(column['label']))
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width

    # Freeze header row
    ws.freeze_panes = 'A2'

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def create_pdf_document(data: list, columns: list, title: str) -> io.BytesIO:
    """Create a PDF document from data"""
    output = io.BytesIO()

    # Use landscape for more columns
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    elements = []

    # Title
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Prepare table data
    table_data = [[col['label'] for col in columns]]

    for row_data in data:
        row = []
        for col in columns:
            value = getattr(row_data, col['field'], None)
            if value is None:
                value = ""
            elif len(str(value)) > 50:
                value = str(value)[:47] + "..."
            row.append(str(value))
        table_data.append(row)

    # Calculate column widths
    available_width = landscape(A4)[0] - 2*cm
    col_width = available_width / len(columns)
    col_widths = [col_width] * len(columns)

    # Create table
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Data style
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E9EDF4')]),
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    output.seek(0)
    return output


# US Export columns
US_COLUMNS = [
    {'field': 'sito', 'label': 'Sito'},
    {'field': 'area', 'label': 'Area'},
    {'field': 'us', 'label': 'US'},
    {'field': 'd_stratigrafica', 'label': 'Def. Stratigrafica'},
    {'field': 'd_interpretativa', 'label': 'Def. Interpretativa'},
    {'field': 'periodo_iniziale', 'label': 'Periodo'},
    {'field': 'fase_iniziale', 'label': 'Fase'},
    {'field': 'datazione', 'label': 'Datazione'},
    {'field': 'descrizione', 'label': 'Descrizione'},
    {'field': 'interpretazione', 'label': 'Interpretazione'},
]

# Materials Export columns
MATERIALI_COLUMNS = [
    {'field': 'sito', 'label': 'Sito'},
    {'field': 'numero_inventario', 'label': 'N. Inventario'},
    {'field': 'tipo_reperto', 'label': 'Tipo'},
    {'field': 'definizione', 'label': 'Definizione'},
    {'field': 'area', 'label': 'Area'},
    {'field': 'us', 'label': 'US'},
    {'field': 'nr_cassa', 'label': 'N. Cassa'},
    {'field': 'luogo_conservazione', 'label': 'Luogo Conserv.'},
    {'field': 'stato_conservazione', 'label': 'Stato Conserv.'},
    {'field': 'datazione_reperto', 'label': 'Datazione'},
    {'field': 'totale_frammenti', 'label': 'Tot. Framm.'},
    {'field': 'peso', 'label': 'Peso (g)'},
]

# Pottery Export columns
POTTERY_COLUMNS = [
    {'field': 'sito', 'label': 'Sito'},
    {'field': 'numero_inventario', 'label': 'N. Inventario'},
    {'field': 'tipo_reperto', 'label': 'Tipo'},
    {'field': 'definizione', 'label': 'Definizione'},
    {'field': 'area', 'label': 'Area'},
    {'field': 'us', 'label': 'US'},
    {'field': 'corpo_ceramico', 'label': 'Corpo Ceramico'},
    {'field': 'rivestimento', 'label': 'Rivestimento'},
    {'field': 'datazione', 'label': 'Datazione'},
    {'field': 'nr_cassa', 'label': 'N. Cassa'},
    {'field': 'peso', 'label': 'Peso (g)'},
]


@router.get("/us/excel")
async def export_us_excel(
    sito: Optional[str] = None,
    area: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export stratigraphic units to Excel"""
    query = db.query(US)

    if sito:
        query = query.filter(US.sito == sito)
    if area:
        query = query.filter(US.area == area)
    if periodo:
        query = query.filter(US.periodo_iniziale == periodo)

    data = query.order_by(US.sito, US.area, US.us).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"US_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}"
    output = create_excel_workbook(data, US_COLUMNS, title)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={title}.xlsx"}
    )


@router.get("/us/pdf")
async def export_us_pdf(
    sito: Optional[str] = None,
    area: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export stratigraphic units to PDF"""
    query = db.query(US)

    if sito:
        query = query.filter(US.sito == sito)
    if area:
        query = query.filter(US.area == area)
    if periodo:
        query = query.filter(US.periodo_iniziale == periodo)

    data = query.order_by(US.sito, US.area, US.us).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"Unità Stratigrafiche - {sito or 'Tutti i siti'}"
    output = create_pdf_document(data, US_COLUMNS[:8], title)  # Limit columns for PDF

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=US_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


@router.get("/materiali/excel")
async def export_materiali_excel(
    sito: Optional[str] = None,
    nr_cassa: Optional[str] = None,
    luogo_conservazione: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export materials inventory to Excel"""
    query = db.query(InventarioMateriali)

    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    if nr_cassa:
        query = query.filter(InventarioMateriali.nr_cassa == nr_cassa)
    if luogo_conservazione:
        query = query.filter(InventarioMateriali.luogo_conservazione == luogo_conservazione)
    if tipo_reperto:
        query = query.filter(InventarioMateriali.tipo_reperto == tipo_reperto)

    data = query.order_by(InventarioMateriali.sito, InventarioMateriali.numero_inventario).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"Materiali_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}"
    output = create_excel_workbook(data, MATERIALI_COLUMNS, title)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={title}.xlsx"}
    )


@router.get("/materiali/pdf")
async def export_materiali_pdf(
    sito: Optional[str] = None,
    nr_cassa: Optional[str] = None,
    luogo_conservazione: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export materials inventory to PDF"""
    query = db.query(InventarioMateriali)

    if sito:
        query = query.filter(InventarioMateriali.sito == sito)
    if nr_cassa:
        query = query.filter(InventarioMateriali.nr_cassa == nr_cassa)
    if luogo_conservazione:
        query = query.filter(InventarioMateriali.luogo_conservazione == luogo_conservazione)
    if tipo_reperto:
        query = query.filter(InventarioMateriali.tipo_reperto == tipo_reperto)

    data = query.order_by(InventarioMateriali.sito, InventarioMateriali.numero_inventario).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"Inventario Materiali - {sito or 'Tutti i siti'}"
    output = create_pdf_document(data, MATERIALI_COLUMNS[:10], title)

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Materiali_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


@router.get("/pottery/excel")
async def export_pottery_excel(
    sito: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    datazione: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export pottery to Excel"""
    query = db.query(Pottery)

    if sito:
        query = query.filter(Pottery.sito == sito)
    if tipo_reperto:
        query = query.filter(Pottery.tipo_reperto == tipo_reperto)
    if datazione:
        query = query.filter(Pottery.datazione.ilike(f"%{datazione}%"))

    data = query.order_by(Pottery.sito, Pottery.numero_inventario).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"Ceramica_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}"
    output = create_excel_workbook(data, POTTERY_COLUMNS, title)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={title}.xlsx"}
    )


@router.get("/pottery/pdf")
async def export_pottery_pdf(
    sito: Optional[str] = None,
    tipo_reperto: Optional[str] = None,
    datazione: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export pottery to PDF"""
    query = db.query(Pottery)

    if sito:
        query = query.filter(Pottery.sito == sito)
    if tipo_reperto:
        query = query.filter(Pottery.tipo_reperto == tipo_reperto)
    if datazione:
        query = query.filter(Pottery.datazione.ilike(f"%{datazione}%"))

    data = query.order_by(Pottery.sito, Pottery.numero_inventario).all()

    if not data:
        raise HTTPException(status_code=404, detail="No data to export")

    title = f"Ceramica - {sito or 'Tutti i siti'}"
    output = create_pdf_document(data, POTTERY_COLUMNS[:9], title)

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Ceramica_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


@router.get("/materiali/summary/excel")
async def export_materials_summary_excel(
    sito: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export materials summary (boxes and storage) to Excel"""
    from collections import defaultdict

    query = db.query(InventarioMateriali)
    if sito:
        query = query.filter(InventarioMateriali.sito == sito)

    all_materials = query.all()

    if not all_materials:
        raise HTTPException(status_code=404, detail="No data to export")

    # Group by storage and box
    storage_data = defaultdict(lambda: defaultdict(list))
    for mat in all_materials:
        storage = mat.luogo_conservazione or "Non specificato"
        box = mat.nr_cassa or "Non specificata"
        storage_data[storage][box].append(mat)

    wb = Workbook()
    ws = wb.active
    ws.title = "Riepilogo Magazzino"

    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    storage_font = Font(bold=True, size=12)
    storage_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")

    row = 1

    # Title
    ws.cell(row=row, column=1, value=f"Riepilogo Magazzino Materiali - {sito or 'Tutti i siti'}")
    ws.cell(row=row, column=1).font = Font(bold=True, size=14)
    row += 2

    for storage_name, boxes in sorted(storage_data.items()):
        # Storage location header
        ws.cell(row=row, column=1, value=f"Luogo: {storage_name}")
        ws.cell(row=row, column=1).font = storage_font
        ws.cell(row=row, column=1).fill = storage_fill
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1

        # Box headers
        headers = ["N. Cassa", "Tot. Reperti", "Tipi", "Peso Tot. (g)", "Tot. Frammenti"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
        row += 1

        # Box data
        for box_name, materials in sorted(boxes.items()):
            types = set(m.tipo_reperto for m in materials if m.tipo_reperto)
            total_weight = sum(m.peso or 0 for m in materials)
            total_fragments = sum(m.totale_frammenti or 0 for m in materials)

            ws.cell(row=row, column=1, value=box_name)
            ws.cell(row=row, column=2, value=len(materials))
            ws.cell(row=row, column=3, value=", ".join(sorted(types)))
            ws.cell(row=row, column=4, value=round(total_weight, 2))
            ws.cell(row=row, column=5, value=total_fragments)
            row += 1

        row += 1  # Empty row between storage locations

    # Auto-adjust column widths
    for col in range(1, 6):
        ws.column_dimensions[get_column_letter(col)].width = 20

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    title = f"Riepilogo_Magazzino_{sito or 'all'}_{datetime.now().strftime('%Y%m%d')}"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={title}.xlsx"}
    )
