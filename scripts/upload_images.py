import io
import os
from typing import Optional

from bson.binary import Binary
from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError

from db import db

# Load environment variables
load_dotenv()

# Get the directory for static images from environment variables
STATIC_IMAGE_DIR = os.getenv("STATIC_IMAGE_DIR")

# File-size/quality tuning (can be overridden via env vars)
MAX_IMAGE_SIZE_MB = float(os.getenv("MAX_IMAGE_SIZE_MB", "15.5"))
MAX_IMAGE_BYTES = int(MAX_IMAGE_SIZE_MB * 1024 * 1024)
IMAGE_QUALITY_START = int(os.getenv("IMAGE_QUALITY_START", "85"))
IMAGE_QUALITY_MIN = int(os.getenv("IMAGE_QUALITY_MIN", "35"))
IMAGE_DOWNSCALE_STEP = float(os.getenv("IMAGE_DOWNSCALE_STEP", "0.9"))
MIN_EDGE_AFTER_DOWNSCALE = int(os.getenv("MIN_EDGE_AFTER_DOWNSCALE", "600"))

# Debug: Print loaded directory
print(f"Loaded STATIC_IMAGE_DIR from environment: {STATIC_IMAGE_DIR}")

# Fallback if not set
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not STATIC_IMAGE_DIR:
    STATIC_IMAGE_DIR = os.path.join(BASE_DIR, "static", "img")
    print(f"STATIC_IMAGE_DIR not set in .env, using default: {STATIC_IMAGE_DIR}")


def _compress_image_to_limit(file_path: str) -> Optional[bytes]:
    """
    Downscale/re-encode the image until it fits under MongoDB's 16 MB document limit.
    Returns raw bytes or None if compression fails.
    """
    try:
        with Image.open(file_path) as img:
            img_format = "JPEG"
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
                img.save(buffer, format=img_format, quality=quality, optimize=True)
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
    """
    Load the image into a Binary blob, compressing it if needed to respect MongoDB's limit.
    """
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


def upload_images():
    # Helper function to upload images to a specified collection
    def upload_to_collection(image_dir, collection_name, save_method, is_empty_method):
        print(f"\nUploading images from {image_dir} to {collection_name} collection...")
        print(f"Image directory: {image_dir}")
        print(f"Directory exists: {os.path.exists(image_dir)}")
        if not os.path.exists(image_dir):
            print("Image directory does not exist! Skipping upload.")
            return

        # List image files
        image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        print(f"Found {len(image_files)} image files: {image_files}")
        if not image_files:
            print("No image files found in directory! Skipping upload.")
            return

        # Check if the collection is empty
        if not is_empty_method():
            print(f"{collection_name} collection is not empty. Skipping image upload.")
            return

        # Upload images
        for image_file in image_files:
            file_path = os.path.join(image_dir, image_file)
            image_blob = _load_image_binary(file_path)
            if not image_blob:
                print(f"Skipping {image_file}: unable to prepare binary under {MAX_IMAGE_SIZE_MB}MB.")
                continue
            try:
                save_method(image_file, image_blob)
                print(f"Uploaded {image_file} to {collection_name}.")
            except Exception as e:
                print(f"Error saving {image_file}: {e}")

    # Upload static images to imgs collection only
    upload_to_collection(
        image_dir=STATIC_IMAGE_DIR,
        collection_name="imgs",
        save_method=db.save_image_to_imgs,
        is_empty_method=db.is_imgs_collection_empty
    )


if __name__ == "__main__":
    upload_images()