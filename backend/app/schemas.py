"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Union
from datetime import date


# Site schemas
class SiteBase(BaseModel):
    sito: Optional[str] = None
    nazione: Optional[str] = None
    regione: Optional[str] = None
    comune: Optional[str] = None
    provincia: Optional[str] = None
    descrizione: Optional[str] = None
    definizione_sito: Optional[str] = None


class SiteResponse(SiteBase):
    id_sito: int

    class Config:
        from_attributes = True


# US schemas
class USBase(BaseModel):
    sito: Optional[str] = None
    area: Optional[str] = None
    us: Optional[str] = None  # text in DB
    d_stratigrafica: Optional[str] = None
    d_interpretativa: Optional[str] = None
    descrizione: Optional[str] = None
    interpretazione: Optional[str] = None
    periodo_iniziale: Optional[str] = None
    fase_iniziale: Optional[str] = None
    periodo_finale: Optional[str] = None
    fase_finale: Optional[str] = None
    datazione: Optional[str] = None
    anno_scavo: Optional[str] = None
    scavato: Optional[str] = None
    order_layer: Optional[int] = None
    unita_tipo: Optional[str] = None
    settore: Optional[str] = None
    quota_min_abs: Optional[float] = None
    quota_max_abs: Optional[float] = None


class USResponse(USBase):
    id_us: int

    class Config:
        from_attributes = True


# Inventario Materiali schemas
class MaterialeBase(BaseModel):
    sito: Optional[str] = None
    numero_inventario: Optional[int] = None
    tipo_reperto: Optional[str] = None
    definizione: Optional[str] = None
    descrizione: Optional[str] = None
    area: Optional[str] = None
    us: Optional[str] = None  # text in DB
    nr_cassa: Optional[int] = None  # bigint in DB
    luogo_conservazione: Optional[str] = None
    stato_conservazione: Optional[str] = None
    datazione_reperto: Optional[str] = None
    lavato: Optional[str] = None
    totale_frammenti: Optional[int] = None
    forme_minime: Optional[int] = None
    forme_massime: Optional[int] = None
    peso: Optional[float] = None
    repertato: Optional[str] = None
    diagnostico: Optional[str] = None


class MaterialeResponse(MaterialeBase):
    id_invmat: int

    class Config:
        from_attributes = True


# Pottery schemas - updated to match pottery_table structure
class PotteryBase(BaseModel):
    sito: Optional[str] = None
    area: Optional[str] = None
    us: Optional[str] = None  # text in DB
    id_number: Optional[int] = None
    box: Optional[int] = None
    photo: Optional[str] = None
    drawing: Optional[str] = None
    anno: Optional[int] = None
    fabric: Optional[str] = None
    percent: Optional[str] = None
    material: Optional[str] = None
    form: Optional[str] = None
    specific_form: Optional[str] = None
    ware: Optional[str] = None
    munsell: Optional[str] = None
    surf_trat: Optional[str] = None
    exdeco: Optional[str] = None
    intdeco: Optional[str] = None
    wheel_made: Optional[str] = None
    descrip_ex_deco: Optional[str] = None
    descrip_in_deco: Optional[str] = None
    note: Optional[str] = None
    diametro_max: Optional[float] = None
    qty: Optional[int] = None
    diametro_rim: Optional[float] = None
    diametro_bottom: Optional[float] = None
    diametro_height: Optional[float] = None
    diametro_preserved: Optional[float] = None
    specific_shape: Optional[str] = None
    bag: Optional[int] = None
    sector: Optional[str] = None


class PotteryResponse(PotteryBase):
    id_rep: int

    class Config:
        from_attributes = True


# Media schemas
class MediaResponse(BaseModel):
    id_media: int
    media_filename: Optional[str] = None
    mediatype: Optional[str] = None
    filetype: Optional[str] = None  # file extension
    media_category: Optional[str] = None  # 'image', 'video', '3d'
    filepath: Optional[str] = None
    path_resize: Optional[str] = None
    thumbnail_url: Optional[str] = None
    full_url: Optional[str] = None

    class Config:
        from_attributes = True


def get_media_category(filename: Optional[str], filetype: Optional[str]) -> str:
    """Determine media category from filename or filetype"""
    if not filename and not filetype:
        return "image"

    # Check extension
    ext = ""
    if filetype:
        ext = filetype.lower().lstrip('.')
    elif filename:
        ext = filename.split('.')[-1].lower() if '.' in filename else ""

    # Image extensions
    if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'tif'):
        return "image"
    # Video extensions
    elif ext in ('mp4', 'webm', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'm4v'):
        return "video"
    # 3D model extensions
    elif ext in ('glb', 'gltf', 'obj', 'fbx', 'stl', 'ply', '3ds', 'dae'):
        return "3d"
    # Default to image
    return "image"


# Summary schemas for materials inventory
class BoxSummary(BaseModel):
    nr_cassa: Union[int, str]  # can be int or string representation
    luogo_conservazione: Optional[str] = None
    total_items: int
    types: List[str] = []


class StorageSummary(BaseModel):
    luogo_conservazione: str
    total_boxes: int
    total_items: int
    boxes: List[BoxSummary] = []


class MaterialsSummary(BaseModel):
    total_materials: int
    total_boxes: int
    storage_locations: List[StorageSummary] = []
    by_type: dict = {}
    by_site: dict = {}


# Pagination
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# Export request
class ExportRequest(BaseModel):
    entity_type: str  # 'us', 'materiali', 'pottery', 'site'
    filters: Optional[dict] = None
    format: str = 'excel'  # 'excel' or 'pdf'


# Authentication schemas
class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
