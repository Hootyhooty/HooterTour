import os
from db import db
from bson.binary import Binary
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define the directory for tour images
TOUR_IMAGE_DIR = os.getenv("TOUR_IMG_DIR")
print(f"Tour image directory: {TOUR_IMAGE_DIR}")
print(f"Tour directory exists: {os.path.exists(TOUR_IMAGE_DIR)}")

def upload_tour_images():
    print(f"\nUploading tour images from {TOUR_IMAGE_DIR} to tour_imgs collection...")

    # Ensure the directory exists
    if not os.path.exists(TOUR_IMAGE_DIR):
        print("Tour image directory does not exist! Cannot proceed with upload.")
        return

    # List image files
    image_files = [f for f in os.listdir(TOUR_IMAGE_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
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
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        print(f"File {image_file} size: {file_size:.2f} MB")
        if file_size > 16:
            print(f"Warning: {image_file} exceeds MongoDB's 16MB document limit. Skipping.")
            continue
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()
                binary_data = Binary(image_data)
                # Save with metadata to identify it as a tour image
                db.save_image_to_tour_imgs(image_file, binary_data, metadata={"type": "tour_image"})
        except Exception as e:
            print(f"Error uploading tour image {image_file}: {e}")

    # Debug: Verify upload
    count_after = collection.count_documents({})
    print(f"tour_imgs collection has {count_after} documents after upload.")

if __name__ == "__main__":
    upload_tour_images()