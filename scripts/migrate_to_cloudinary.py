#!/usr/bin/env python3
"""
Migration script to upload media files to Cloudinary
Only uploads files that have associations in the database
"""

import os
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
import cloudinary
import cloudinary.uploader
import psycopg2
from pathlib import Path
import time

# Configuration
CLOUDINARY_CLOUD_NAME = "dkioeufik"
CLOUDINARY_API_KEY = "531811383456143"
CLOUDINARY_API_SECRET = "TZ8qlfL3_1M75okhTL2XmP4X_ZY"

# Local paths
PHOTOLOG_BASE = "/Volumes/TOSHIBA EXT/khtum2023/photolog"
THUMBNAIL_PATH = os.path.join(PHOTOLOG_BASE, "thumbnail")
ORIGINAL_PATH = os.path.join(PHOTOLOG_BASE, "original")

# Database connection (local)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "pyarchinit",
    "user": "postgres",
    "password": "postgres"
}

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)


def get_all_media(conn):
    """Get ALL UNIQUE media, deduplicating by id_media"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT mt.id_media, mt.media_filename, mt.filepath, mt.path_resize
        FROM media_thumb_table mt
        ORDER BY mt.id_media
    """)

    # Deduplicate by id_media, keeping all variants so we can pick the one that exists
    media_dict = {}
    for row in cursor.fetchall():
        id_media = row[0]
        if id_media not in media_dict:
            media_dict[id_media] = []
        media_dict[id_media].append(row)

    return media_dict


def find_file_on_disk(filepath, folder_path):
    """Find a file on disk, handling various naming conventions"""
    if not filepath:
        return None

    full_path = os.path.join(folder_path, filepath)
    if os.path.exists(full_path):
        return full_path

    # Try without path prefix
    filename = os.path.basename(filepath)
    full_path = os.path.join(folder_path, filename)
    if os.path.exists(full_path):
        return full_path

    return None


def upload_to_cloudinary(file_path, public_id, folder, resource_type="image"):
    """Upload a file to Cloudinary"""
    try:
        result = cloudinary.uploader.upload(
            file_path,
            public_id=public_id,
            folder=folder,
            resource_type=resource_type,
            overwrite=True,
            invalidate=True
        )
        return result
    except Exception as e:
        print(f"  Error uploading {file_path}: {e}")
        return None


def find_best_file_for_media(media_variants, thumbnail_path, original_path):
    """
    Given multiple variants of the same id_media, find the one that has files on disk.
    Returns (id_media, media_filename, thumb_file, orig_file)
    """
    for id_media, media_filename, filepath, path_resize in media_variants:
        thumb_file = find_file_on_disk(filepath, thumbnail_path)

        # Find original
        original_filepath = path_resize or filepath
        orig_file = None
        if original_filepath:
            original_name = original_filepath.replace("_thumb", "")
            orig_file = find_file_on_disk(original_name, original_path)

        # If we found at least one file, use this variant
        if thumb_file or orig_file:
            return (id_media, media_filename, thumb_file, orig_file)

    # No files found for any variant
    return (media_variants[0][0], media_variants[0][1], None, None)


def migrate_media():
    """Main migration function"""
    print("=" * 60)
    print("PyArchInit Media Migration to Cloudinary")
    print("=" * 60)

    # Check paths exist
    if not os.path.exists(PHOTOLOG_BASE):
        print(f"ERROR: Photolog path not found: {PHOTOLOG_BASE}")
        print("Make sure the external drive is connected.")
        sys.exit(1)

    print(f"\nSource paths:")
    print(f"  Thumbnails: {THUMBNAIL_PATH}")
    print(f"  Originals:  {ORIGINAL_PATH}")

    # Connect to database
    print("\nConnecting to database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("  Connected!")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # Get ALL media (now returns dict keyed by id_media)
    print("\nFetching all media...")
    media_dict = get_all_media(conn)
    total_unique = len(media_dict)
    print(f"  Found {total_unique} unique media IDs")

    # Statistics
    stats = {
        "total": total_unique,
        "thumbnails_found": 0,
        "thumbnails_uploaded": 0,
        "originals_found": 0,
        "errors": 0,
        "skipped": 0
    }

    # Process each unique media
    print("\nStarting upload...")
    print("-" * 60)

    start_time = time.time()
    media_ids = sorted(media_dict.keys())

    for i, id_media in enumerate(media_ids):
        variants = media_dict[id_media]
        progress = f"[{i+1}/{total_unique}]"

        # Find the best variant (one with files on disk)
        id_media, media_filename, thumb_file, orig_file = find_best_file_for_media(
            variants, THUMBNAIL_PATH, ORIGINAL_PATH
        )

        # Upload thumbnail only (originals stay on storage server to avoid size limits)
        if thumb_file:
            stats["thumbnails_found"] += 1
            public_id = f"thumb/{id_media}_{media_filename}"
            print(f"{progress} Uploading thumbnail: {os.path.basename(thumb_file)}")

            result = upload_to_cloudinary(thumb_file, public_id, "pyarchinit/thumbnails")
            if result:
                stats["thumbnails_uploaded"] += 1
            else:
                stats["errors"] += 1
        else:
            stats["skipped"] += 1

        # Track originals found (for info) but don't upload
        if orig_file:
            stats["originals_found"] += 1

        # Progress update every 100 files
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (total_unique - i - 1) / rate if rate > 0 else 0
            print(f"\n  Progress: {i+1}/{total_unique} ({(i+1)/total_unique*100:.1f}%)")
            print(f"  Elapsed: {elapsed/60:.1f} min, Remaining: ~{remaining/60:.1f} min\n")

    # Final statistics
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"\nStatistics:")
    print(f"  Total unique media IDs: {stats['total']}")
    print(f"  Thumbnails found: {stats['thumbnails_found']}")
    print(f"  Thumbnails uploaded: {stats['thumbnails_uploaded']}")
    print(f"  Originals found (not uploaded): {stats['originals_found']}")
    print(f"  Skipped (no files): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"\nTime elapsed: {elapsed/60:.1f} minutes")

    conn.close()

    print("\nMigration Strategy:")
    print("  - Thumbnails: Uploaded to Cloudinary for fast CDN delivery")
    print("  - Originals: Kept on storage server (many exceed 10MB Cloudinary limit)")
    print("\nNext steps:")
    print("1. Update the backend to use direct Cloudinary URLs for thumbnails")
    print("2. Thumbnails URL: https://res.cloudinary.com/dkioeufik/image/upload/pyarchinit/thumbnails/thumb/{id}_{filename}")


if __name__ == "__main__":
    # Check for dry-run flag
    if "--dry-run" in sys.argv:
        print("DRY RUN MODE - No files will be uploaded")
        # Just show what would be done
        conn = psycopg2.connect(**DB_CONFIG)
        media_dict = get_all_media(conn)
        print(f"Would upload {len(media_dict)} unique media IDs")

        found_thumbs = 0
        found_origs = 0
        media_ids = sorted(media_dict.keys())[:20]

        for id_media in media_ids:
            variants = media_dict[id_media]
            id_m, filename, thumb_file, orig_file = find_best_file_for_media(
                variants, THUMBNAIL_PATH, ORIGINAL_PATH
            )
            if thumb_file:
                found_thumbs += 1
            if orig_file:
                found_origs += 1
            print(f"  {id_media}: thumb={'YES' if thumb_file else 'NO'}, orig={'YES' if orig_file else 'NO'} - {filename}")

        print(f"\nSample (first 20): {found_thumbs} thumbs, {found_origs} origs found")
        conn.close()
    else:
        migrate_media()
