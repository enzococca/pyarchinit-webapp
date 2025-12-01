"""
API routes for Media files
Integrates with PyArchInit Storage Server for remote media access
With in-memory caching for improved performance
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Tuple, Dict, Any
import httpx
import io
import time
import asyncio

from ..database import get_db
from ..models import MediaThumb, MediaToEntity
from ..schemas import MediaResponse, get_media_category
from ..config import settings

router = APIRouter(prefix="/media", tags=["Media"])


# Simple TTL Cache implementation without external dependencies
class SimpleTTLCache:
    """Simple TTL cache using dict with timestamp tracking"""

    def __init__(self, maxsize: int = 100, ttl: int = 3600):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, timestamp: float) -> bool:
        return time.time() - timestamp > self.ttl

    def _cleanup(self):
        """Remove expired entries and enforce maxsize"""
        now = time.time()
        # Remove expired
        expired_keys = [k for k, (_, ts) in self._cache.items() if now - ts > self.ttl]
        for k in expired_keys:
            del self._cache[k]

        # Enforce maxsize - remove oldest entries
        if len(self._cache) > self.maxsize:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_items[:len(self._cache) - self.maxsize]:
                del self._cache[k]

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if not self._is_expired(timestamp):
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        self._cleanup()
        self._cache[key] = (value, time.time())

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self._cleanup()
        return len(self._cache)

    def clear(self):
        self._cache.clear()


# In-memory cache for images
# Max 500 items, 1 hour TTL for thumbnails, 30 min for full images
thumbnail_cache = SimpleTTLCache(maxsize=500, ttl=3600)  # 1 hour
full_image_cache = SimpleTTLCache(maxsize=100, ttl=1800)  # 30 min
cache_lock = asyncio.Lock()


def get_storage_url(filepath: str, is_thumbnail: bool = True) -> str:
    """Generate direct URL for media file from storage server"""
    if not filepath:
        return None

    base_url = settings.STORAGE_SERVER_URL.rstrip('/')
    folder = "thumbnail" if is_thumbnail else "original"

    # If filepath already contains the folder, use it as is
    if filepath.startswith('/'):
        filepath = filepath[1:]

    return f"{base_url}/files/{folder}/{filepath}"


def get_public_proxy_url(filepath: str, is_thumbnail: bool = True) -> str:
    """Generate URL for our public proxy endpoint that Cloudinary can fetch from"""
    if not filepath:
        return None

    base_url = settings.BACKEND_PUBLIC_URL.rstrip('/')
    folder = "thumbnail" if is_thumbnail else "original"

    if filepath.startswith('/'):
        filepath = filepath[1:]

    return f"{base_url}/api/media/public/{folder}/{filepath}"


def get_cloudinary_url(filepath: str, is_thumbnail: bool = True) -> str:
    """Generate Cloudinary fetch URL for optimized image delivery"""
    if not filepath:
        return None

    cloud_name = settings.CLOUDINARY_CLOUD_NAME

    if is_thumbnail:
        # Thumbnail: small size, auto format, auto quality
        transformations = "f_auto,q_auto,w_150,h_150,c_fill"
    else:
        # Full image: larger size, good quality, auto format
        transformations = "f_auto,q_auto:good,w_1200,c_limit"

    # Get URL through our public proxy (which has storage server auth)
    proxy_url = get_public_proxy_url(filepath, is_thumbnail)

    # URL encode the proxy URL
    import urllib.parse
    encoded_url = urllib.parse.quote(proxy_url, safe='')

    return f"https://res.cloudinary.com/{cloud_name}/image/fetch/{transformations}/{encoded_url}"


def get_media_url(filepath: str, is_thumbnail: bool = True, media_cat: str = "image") -> str:
    """Generate URL for media file - uses Cloudinary if enabled (for images only)"""
    if not filepath:
        return None

    # Only use Cloudinary for images (not for video or 3D)
    if settings.CLOUDINARY_ENABLED and media_cat == "image":
        return get_cloudinary_url(filepath, is_thumbnail)

    # For video/3D or when Cloudinary is disabled, use public proxy URL
    return get_public_proxy_url(filepath, is_thumbnail)


async def fetch_and_cache_image(
    url: str,
    cache: SimpleTTLCache,
    cache_key: str
) -> Tuple[bytes, str]:
    """Fetch image from storage server and cache it"""
    # Check cache first
    async with cache_lock:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    # Fetch from storage server
    async with httpx.AsyncClient() as client:
        headers = {}
        if settings.STORAGE_API_KEY:
            headers["X-API-Key"] = settings.STORAGE_API_KEY

        response = await client.get(url, headers=headers, timeout=60.0)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch image: {response.status_code}"
            )

        content_type = response.headers.get("content-type", "image/jpeg")
        image_data = (response.content, content_type)

        # Store in cache
        async with cache_lock:
            cache.set(cache_key, image_data)

        return image_data


# Public proxy endpoint for Cloudinary to fetch images (no auth required)
@router.get("/public/{folder}/{filepath:path}")
async def public_image_proxy(folder: str, filepath: str):
    """
    Public proxy endpoint for CDN/Cloudinary to fetch images.
    This endpoint fetches from the storage server with API key authentication
    and returns the image publicly (for CDN caching).

    folder: 'thumbnail' or 'original'
    filepath: the image path
    """
    if folder not in ("thumbnail", "original"):
        raise HTTPException(status_code=400, detail="Invalid folder. Use 'thumbnail' or 'original'")

    # Build storage server URL
    base_url = settings.STORAGE_SERVER_URL.rstrip('/')
    url = f"{base_url}/files/{folder}/{filepath}"

    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if settings.STORAGE_API_KEY:
                headers["X-API-Key"] = settings.STORAGE_API_KEY

            response = await client.get(url, headers=headers, timeout=60.0)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Image not found or unavailable"
                )

            content_type = response.headers.get("content-type", "image/jpeg")

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=31536000",  # 1 year cache for CDN
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")


@router.get("/categories")
async def get_media_categories():
    """Get available media categories for filtering"""
    return {
        "categories": [
            {"id": "all", "name": "All Media", "icon": "bi-collection"},
            {"id": "image", "name": "Images", "icon": "bi-image"},
            {"id": "video", "name": "Videos", "icon": "bi-camera-video"},
            {"id": "3d", "name": "3D Models", "icon": "bi-box"}
        ]
    }


@router.get("/for-entity/{entity_type}/{entity_id}", response_model=List[MediaResponse])
async def get_media_for_entity(
    entity_type: str,
    entity_id: int,
    category: Optional[str] = Query(None, description="Filter by media category: image, video, 3d"),
    db: Session = Depends(get_db)
):
    """
    Get all media associated with an entity.
    entity_type: US, REPERTO, CERAMICA, etc.
    category: Optional filter by media_category (image, video, 3d)
    """
    # Query media associations
    associations = db.query(MediaToEntity).filter(
        MediaToEntity.entity_type == entity_type.upper(),
        MediaToEntity.id_entity == entity_id
    ).all()

    media_list = []
    for assoc in associations:
        # Get thumbnail info
        thumb = db.query(MediaThumb).filter(
            MediaThumb.id_media == assoc.id_media
        ).first()

        if thumb:
            media_cat = get_media_category(thumb.media_filename, thumb.filetype)

            # Filter by category if specified
            if category and category != "all" and media_cat != category:
                continue

            media_list.append(MediaResponse(
                id_media=thumb.id_media,
                media_filename=thumb.media_filename,
                mediatype=thumb.mediatype,
                filetype=thumb.filetype,
                media_category=media_cat,
                filepath=thumb.filepath,
                path_resize=thumb.path_resize,
                thumbnail_url=get_media_url(thumb.filepath, is_thumbnail=True, media_cat=media_cat),
                full_url=get_media_url(thumb.path_resize or thumb.filepath, is_thumbnail=False, media_cat=media_cat)
            ))

    return media_list


@router.get("/thumbnail/{media_id}")
async def get_thumbnail(media_id: int, db: Session = Depends(get_db)):
    """Get thumbnail - redirects to Cloudinary if enabled, otherwise proxies"""
    from fastapi.responses import RedirectResponse

    thumb = db.query(MediaThumb).filter(MediaThumb.id_media == media_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Media not found")

    url = get_media_url(thumb.filepath, is_thumbnail=True)
    if not url:
        raise HTTPException(status_code=404, detail="Thumbnail path not available")

    # If Cloudinary is enabled, redirect directly to Cloudinary URL
    if settings.CLOUDINARY_ENABLED:
        return RedirectResponse(url=url, status_code=302)

    # Otherwise, proxy through backend with caching
    cache_key = f"thumb_{media_id}"

    try:
        image_data, content_type = await fetch_and_cache_image(
            url, thumbnail_cache, cache_key
        )

        return Response(
            content=image_data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # 24 hours browser cache
                "X-Cache": "HIT" if cache_key in thumbnail_cache else "MISS"
            }
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching thumbnail: {str(e)}")


@router.get("/full/{media_id}")
async def get_full_image(media_id: int, db: Session = Depends(get_db)):
    """Get full image - redirects to Cloudinary if enabled, otherwise proxies"""
    from fastapi.responses import RedirectResponse

    thumb = db.query(MediaThumb).filter(MediaThumb.id_media == media_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Media not found")

    filepath = thumb.path_resize or thumb.filepath
    url = get_media_url(filepath, is_thumbnail=False)
    if not url:
        raise HTTPException(status_code=404, detail="Image path not available")

    # If Cloudinary is enabled, redirect directly to Cloudinary URL
    if settings.CLOUDINARY_ENABLED:
        return RedirectResponse(url=url, status_code=302)

    # Otherwise, proxy through backend with caching
    cache_key = f"full_{media_id}"

    try:
        image_data, content_type = await fetch_and_cache_image(
            url, full_image_cache, cache_key
        )

        return Response(
            content=image_data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # 24 hours browser cache
                "X-Cache": "HIT" if cache_key in full_image_cache else "MISS"
            }
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache and CDN statistics"""
    return {
        "cloudinary": {
            "enabled": settings.CLOUDINARY_ENABLED,
            "cloud_name": settings.CLOUDINARY_CLOUD_NAME if settings.CLOUDINARY_ENABLED else None
        },
        "thumbnail_cache": {
            "size": len(thumbnail_cache),
            "maxsize": thumbnail_cache.maxsize,
            "ttl": thumbnail_cache.ttl
        },
        "full_image_cache": {
            "size": len(full_image_cache),
            "maxsize": full_image_cache.maxsize,
            "ttl": full_image_cache.ttl
        }
    }


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all image caches"""
    async with cache_lock:
        thumbnail_cache.clear()
        full_image_cache.clear()
    return {"message": "Cache cleared"}


@router.get("/list")
async def list_media(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    mediatype: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all media files"""
    query = db.query(MediaThumb)

    if mediatype:
        query = query.filter(MediaThumb.mediatype == mediatype)

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    media_items = []
    for m in items:
        media_cat = get_media_category(m.media_filename, m.filetype)
        media_items.append(MediaResponse(
            id_media=m.id_media,
            media_filename=m.media_filename,
            mediatype=m.mediatype,
            filetype=m.filetype,
            media_category=media_cat,
            filepath=m.filepath,
            path_resize=m.path_resize,
            thumbnail_url=get_media_url(m.filepath, is_thumbnail=True, media_cat=media_cat),
            full_url=get_media_url(m.path_resize or m.filepath, is_thumbnail=False, media_cat=media_cat)
        ))

    return {
        "total": total,
        "items": media_items
    }


@router.get("/search")
async def search_media_with_associations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    media_category: Optional[str] = Query(None, description="Filter by category: image, video, 3d"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type: US, REPERTO, CERAMICA"),
    filename: Optional[str] = Query(None, description="Search by filename"),
    db: Session = Depends(get_db)
):
    """
    Search media files with their entity associations.
    Returns media info along with which entities they belong to.
    """
    from sqlalchemy import or_

    # Base query joining media with associations
    query = db.query(MediaThumb, MediaToEntity).outerjoin(
        MediaToEntity, MediaThumb.id_media == MediaToEntity.id_media
    )

    # Filter by entity type
    if entity_type:
        query = query.filter(MediaToEntity.entity_type == entity_type.upper())

    # Filter by filename
    if filename:
        query = query.filter(MediaThumb.media_filename.ilike(f"%{filename}%"))

    # Get results
    results = query.offset(skip).limit(limit).all()

    # Process and filter by media_category
    media_list = []
    seen_ids = set()

    for thumb, assoc in results:
        if thumb.id_media in seen_ids:
            continue

        media_cat = get_media_category(thumb.media_filename, thumb.filetype)

        # Filter by category if specified
        if media_category and media_category != media_cat:
            continue

        seen_ids.add(thumb.id_media)

        # Get all associations for this media
        associations = db.query(MediaToEntity).filter(
            MediaToEntity.id_media == thumb.id_media
        ).all()

        entity_info = []
        for a in associations:
            entity_info.append({
                "entity_type": a.entity_type,
                "id_entity": a.id_entity
            })

        media_list.append({
            "id_media": thumb.id_media,
            "media_filename": thumb.media_filename,
            "mediatype": thumb.mediatype,
            "filetype": thumb.filetype,
            "media_category": media_cat,
            "thumbnail_url": get_media_url(thumb.filepath, is_thumbnail=True, media_cat=media_cat),
            "full_url": get_media_url(thumb.path_resize or thumb.filepath, is_thumbnail=False, media_cat=media_cat),
            "entities": entity_info
        })

    # Get statistics
    total_images = sum(1 for m in media_list if m["media_category"] == "image")
    total_videos = sum(1 for m in media_list if m["media_category"] == "video")
    total_3d = sum(1 for m in media_list if m["media_category"] == "3d")

    return {
        "total": len(media_list),
        "statistics": {
            "images": total_images,
            "videos": total_videos,
            "models_3d": total_3d
        },
        "items": media_list
    }


@router.get("/statistics")
async def get_media_statistics(db: Session = Depends(get_db)):
    """Get media statistics"""
    total = db.query(func.count(MediaThumb.id_media_thumb)).scalar()

    by_type = db.query(
        MediaThumb.mediatype,
        func.count(MediaThumb.id_media_thumb).label('count')
    ).group_by(MediaThumb.mediatype).all()

    # Count associations by entity type
    by_entity = db.query(
        MediaToEntity.entity_type,
        func.count(MediaToEntity.id_mediaToEntity).label('count')
    ).group_by(MediaToEntity.entity_type).all()

    return {
        "total_media": total,
        "by_type": {t[0] or "unknown": t[1] for t in by_type},
        "by_entity_type": {e[0] or "unknown": e[1] for e in by_entity}
    }


@router.get("/{media_id}", response_model=MediaResponse)
async def get_media_info(media_id: int, db: Session = Depends(get_db)):
    """Get media info by ID"""
    thumb = db.query(MediaThumb).filter(MediaThumb.id_media == media_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Media not found")

    media_cat = get_media_category(thumb.media_filename, thumb.filetype)
    return MediaResponse(
        id_media=thumb.id_media,
        media_filename=thumb.media_filename,
        mediatype=thumb.mediatype,
        filetype=thumb.filetype,
        media_category=media_cat,
        filepath=thumb.filepath,
        path_resize=thumb.path_resize,
        thumbnail_url=get_media_url(thumb.filepath, is_thumbnail=True, media_cat=media_cat),
        full_url=get_media_url(thumb.path_resize or thumb.filepath, is_thumbnail=False, media_cat=media_cat)
    )
