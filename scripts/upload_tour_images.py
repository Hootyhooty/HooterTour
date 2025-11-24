import io
import os
from typing import Optional

from bson.binary import Binary
from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError

from db import db

# Load environment variables
load_dotenv()

# Define the directory for tour images
TOUR_IMAGE_DIR = os.getenv("TOUR_IMG_DIR")
MAX_IMAGE_SIZE_MB = float(os.getenv("MAX_IMAGE_SIZE_MB", "15.5"))
MAX_IMAGE_BYTES = int(MAX_IMAGE_SIZE_MB * 1024 * 1024)
IMAGE_QUALITY_START = int(os.getenv("IMAGE_QUALITY_START", "85"))
IMAGE_QUALITY_MIN = int(os.getenv("IMAGE_QUALITY_MIN", "35"))
IMAGE_DOWNSCALE_STEP = float(os.getenv("IMAGE_DOWNSCALE_STEP", "0.9"))
MIN_EDGE_AFTER_DOWNSCALE = int(os.getenv("MIN_EDGE_AFTER_DOWNSCALE", "600"))

print(f"Tour image directory: {TOUR_IMAGE_DIR}")
print(f"Tour directory exists: {os.path.exists(TOUR_IMAGE_DIR)}")


def _compress_image_to_limit(file_path: str) -> Optional[bytes]:
    try:
        with Image.open(file_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            else:
                img = img.convert("RGB")

            width, height = img.size
            quality = IMAGE_QUALITY_START
            buffer = io.BytesIO()

            while True:
                buffer.seek(0)
                buffer.truncate()
                img.save(buffer, format="JPEG", optimize=True, quality=quality)
                current_size = buffer.tell()
                print(f"Compressed {os.path.basename(file_path)} -> {current_size / (1024 * 1024):.2f} MB at quality {quality}")
                if current_size <= MAX_IMAGE_BYTES:
                    return buffer.getvalue()

                if quality > IMAGE_QUALITY_MIN:
                    quality = max(quality - 5, IMAGE_QUALITY_MIN)
                    continue

                new_width = int(width * IMAGE_DOWNSCALE_STEP)
                new_height = int(height * IMAGE_DOWNSCALE_STEP)

                if new_width < MIN_EDGE_AFTER_DOWNSCALE or new_height < MIN_EDGE_AFTER_DOWNSCALE:
                    print(f"Unable to shrink {file_path} below {MAX_IMAGE_SIZE_MB}MB without going under minimum dimensions.")
                    return None

                img = img.resize((new_width, new_height), Image.LANCZOS)
                width, height = img.size
    except UnidentifiedImageError:
        print(f"Unsupported image format for {file_path}. Skipping.")
        return None
    except Exception as exc:
        print(f"Failed to compress {file_path}: {exc}")
        return None


def _load_image_binary(file_path: str) -> Optional[Binary]:
    try:
        raw_size = os.path.getsize(file_path)
    except OSError as exc:
        print(f"Could not stat file {file_path}: {exc}")
        return None

    if raw_size <= MAX_IMAGE_BYTES:
        try:
            with open(file_path, "rb") as f:
                return Binary(f.read())
        except Exception as exc:
            print(f"Failed to read {file_path}: {exc}")
            return None

    print(f"{os.path.basename(file_path)} is {raw_size / (1024 * 1024):.2f} MB, attempting to compress...")
    compressed = _compress_image_to_limit(file_path)
    if compressed is None:
        return None
    return Binary(compressed)


def upload_tour_images():
    print(f"\nUploading tour images from {TOUR_IMAGE_DIR} to tour_imgs collection...")

    # Ensure the directory exists
    if not TOUR_IMAGE_DIR or not os.path.exists(TOUR_IMAGE_DIR):
        print("Tour image directory does not exist! Cannot proceed with upload.")
        return

    # List image files
    image_files = [f for f in os.listdir(TOUR_IMAGE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Found {len(image_files)} tour image files: {image_files}")
    if not image_files:
        print("No tour image files found in directory! Nothing to upload.")
        return

    # Debug: Log the state of the collection before upload
    collection = db.get_tour_imgs_collection()
    count = collection.count_documents({})
    print(f"tour_imgs collection has {count} documents before upload.")

    # Clear the tour_imgs collection to avoid duplicates (optional, since no conditions)
    collection.drop()
    print("Cleared tour_imgs collection before uploading new images.")

    # Upload all tour images unconditionally
    for image_file in image_files:
        file_path = os.path.join(TOUR_IMAGE_DIR, image_file)
        image_blob = _load_image_binary(file_path)
        if not image_blob:
            print(f"Skipping {image_file}: unable to prepare binary under {MAX_IMAGE_SIZE_MB}MB.")
            continue
        try:
            # Save with metadata to identify it as a tour image
            db.save_image_to_tour_imgs(image_file, image_blob, metadata={"type": "tour_image"})
        except Exception as e:
            print(f"Error uploading tour image {image_file}: {e}")

    # Debug: Verify upload
    count_after = collection.count_documents({})
    print(f"tour_imgs collection has {count_after} documents after upload.")


if __name__ == "__main__":
    upload_tour_images()