import os
from db import db
from bson.binary import Binary
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the directory for static images from environment variables
STATIC_IMAGE_DIR = os.getenv("STATIC_IMAGE_DIR")

# Debug: Print loaded directory
print(f"Loaded STATIC_IMAGE_DIR from environment: {STATIC_IMAGE_DIR}")

# Fallback if not set
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not STATIC_IMAGE_DIR:
    STATIC_IMAGE_DIR = os.path.join(BASE_DIR, "static", "img")
    print(f"STATIC_IMAGE_DIR not set in .env, using default: {STATIC_IMAGE_DIR}")

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
        image_files = [f for f in os.listdir(image_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
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
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
            print(f"File {image_file} size: {file_size:.2f} MB")
            if file_size > 16:
                print(f"Warning: {image_file} exceeds MongoDB's 16MB document limit. Skipping.")
                continue
            try:
                with open(file_path, "rb") as f:
                    image_data = f.read()
                    binary_data = Binary(image_data)
                    save_method(image_file, binary_data)
            except Exception as e:
                print(f"Error reading file {image_file}: {e}")

    # Upload static images to imgs collection only
    upload_to_collection(
        image_dir=STATIC_IMAGE_DIR,
        collection_name="imgs",
        save_method=db.save_image_to_imgs,
        is_empty_method=db.is_imgs_collection_empty
    )

if __name__ == "__main__":
    upload_images()