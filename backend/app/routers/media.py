"""
API routes for Media files
Integrates with PyArchInit Storage Server for remote media access
With in-memory caching for improved performance
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Tuple
import httpx
import io
import hashlib
from cachetools import TTLCache
import asyncio

from ..database import get_db
from ..models import MediaThumb, MediaToEntity
from ..schemas import MediaResponse
from ..config import settings

router = APIRouter(prefix="/media", tags=["Media"])

# In-memory cache for images
# Max 500 items, 1 hour TTL for thumbnails, 30 min for full images
thumbnail_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)  # 1 hour
full_image_cache: TTLCache = TTLCache(maxsize=100, ttl=1800)  # 30 min
cache_lock = asyncio.Lock()


def get_media_url(filepath: str, is_thumbnail: bool = True) -> str:
    """Generate full URL for media file from storage server"""
    if not filepath:
        return None

    base_url = settings.STORAGE_SERVER_URL.rstrip('/')
    folder = "thumbnail" if is_thumbnail else "original"

    # If filepath already contains the folder, use it as is
    if filepath.startswith('/'):
        filepath = filepath[1:]

    return f"{base_url}/files/{folder}/{filepath}"


async def fetch_and_cache_image(
    url: str,
    cache: TTLCache,
    cache_key: str
) -> Tuple[bytes, str]:
    """Fetch image from storage server and cache it"""
    # Check cache first
    async with cache_lock:
        if cache_key in cache:
            return cache[cache_key]

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
            cache[cache_key] = image_data

        return image_data


@router.get("/for-entity/{entity_type}/{entity_id}", response_model=List[MediaResponse])
async def get_media_for_entity(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all media associated with an entity.
    entity_type: US, REPERTO, CERAMICA, etc.
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
            media_list.append(MediaResponse(
                id_media=thumb.id_media,
                media_filename=thumb.media_filename,
                mediatype=thumb.mediatype,
                filepath=thumb.filepath,
                path_resize=thumb.path_resize,
                thumbnail_url=get_media_url(thumb.filepath, is_thumbnail=True),
                full_url=get_media_url(thumb.path_resize or thumb.filepath, is_thumbnail=False)
            ))

    return media_list


@router.get("/thumbnail/{media_id}")
async def get_thumbnail(media_id: int, db: Session = Depends(get_db)):
    """Proxy endpoint to get thumbnail from storage server (with caching)"""
    thumb = db.query(MediaThumb).filter(MediaThumb.id_media == media_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Media not found")

    url = get_media_url(thumb.filepath, is_thumbnail=True)
    if not url:
        raise HTTPException(status_code=404, detail="Thumbnail path not available")

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
    """Proxy endpoint to get full image from storage server (with caching)"""
    thumb = db.query(MediaThumb).filter(MediaThumb.id_media == media_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Media not found")

    filepath = thumb.path_resize or thumb.filepath
    url = get_media_url(filepath, is_thumbnail=False)
    if not url:
        raise HTTPException(status_code=404, detail="Image path not available")

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
    """Get cache statistics"""
    return {
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

    return {
        "total": total,
        "items": [
            MediaResponse(
                id_media=m.id_media,
                media_filename=m.media_filename,
                mediatype=m.mediatype,
                filepath=m.filepath,
                path_resize=m.path_resize,
                thumbnail_url=get_media_url(m.filepath, is_thumbnail=True),
                full_url=get_media_url(m.path_resize or m.filepath, is_thumbnail=False)
            ) for m in items
        ]
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

    return MediaResponse(
        id_media=thumb.id_media,
        media_filename=thumb.media_filename,
        mediatype=thumb.mediatype,
        filepath=thumb.filepath,
        path_resize=thumb.path_resize,
        thumbnail_url=get_media_url(thumb.filepath, is_thumbnail=True),
        full_url=get_media_url(thumb.path_resize or thumb.filepath, is_thumbnail=False)
    )
