from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from dotenv import load_dotenv
import os
from mongoengine import connect
from bson.binary import Binary

# Load environment variables
load_dotenv()

class Database:
    def __init__(self):
        self.connection_string = os.getenv('MONGODB_URI')
        self.client = None
        self.db = None
        self.users_collection = None
        self.tours_collection = None
        self.reviews_collection = None
        self.user_imgs_collection = None
        self.imgs_collection = None
        # self.tour_imgs_collection = None  # Commented out: No longer using tour_imgs
        self.all_users = []
        self.connect()

    def connect(self):
        try:
            print(f"Connecting to MongoDB with URI: {self.connection_string}")
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client['tourist_db']
            self.users_collection = self.db['users']
            self.tours_collection = self.db['tours']
            self.reviews_collection = self.db['reviews']
            self.user_imgs_collection = self.db['user_imgs']
            self.imgs_collection = self.db['imgs']
            # self.tour_imgs_collection = self.db['tour_imgs']  # Commented out: No longer using tour_imgs
            print(f"Initialized collections: users={self.users_collection}, tours={self.tours_collection}, reviews={self.reviews_collection}, user_imgs={self.user_imgs_collection}, imgs={self.imgs_collection}")
            print("DB connection successful!")

            connect(db='tourist_db', host=self.connection_string)
            print("MongoEngine connection successful!")
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
        except ConfigurationError as e:
            print(f"DNS resolution error: {e}. Please check your connection string and network settings.")
            raise

    def get_imgs_collection(self):
        print("Getting imgs collection...")
        if self.imgs_collection is None:
            print("Imgs collection is None, connecting...")
            self.connect()
        print(f"Returning imgs collection: {self.imgs_collection}")
        return self.imgs_collection

    def save_image_to_imgs(self, filename, image_data, metadata=None):
        """Save an image to the imgs collection with optional metadata."""
        try:
            collection = self.get_imgs_collection()
            print(f"Collection accessible: {collection is not None}")
            if collection is None:
                print("Imgs collection is None! Cannot save image.")
                return False

            # Check if the image already exists
            existing = collection.find_one({"filename": filename})
            print(f"Checking for existing image {filename}: {existing is not None}")
            image_doc = {
                "filename": filename,
                "data": image_data,
                "metadata": metadata or {}
            }
            if existing:
                # Update existing image
                collection.update_one(
                    {"filename": filename},
                    {"$set": image_doc}
                )
                print(f"Updated image {filename} in imgs collection.")
            else:
                # Insert new image
                collection.insert_one(image_doc)
                print(f"Saved image {filename} to imgs collection.")
            return True
        except Exception as e:
            print(f"Error saving image {filename}: {e}")
            return False

    def get_image_by_filename(self, filename):
        """Retrieve an image from the imgs collection by filename."""
        try:
            collection = self.get_imgs_collection()
            if collection is None:
                raise ValueError("Imgs collection is not initialized.")
            image_doc = collection.find_one({"filename": filename})
            if not image_doc:
                print(f"No image found with filename {filename}")
                return None
            return image_doc
        except Exception as e:
            print(f"Error retrieving image {filename}: {e}")
            return None

    def is_imgs_collection_empty(self):
        try:
            collection = self.get_imgs_collection()
            if collection is None:
                raise ValueError("Imgs collection is not initialized.")
            count = collection.count_documents({})
            print(f"Imgs collection has {count} documents. Empty: {count == 0}")
            return count == 0
        except Exception as e:
            print(f"Error checking imgs collection: {e}")
            return False

    # Commented out: Methods related to tour_imgs (no longer used)
    # def get_tour_imgs_collection(self):
    #     print("Getting tour_imgs collection...")
    #     if self.tour_imgs_collection is None:
    #         print("Tour_imgs collection is None, connecting...")
    #         self.connect()
    #     print(f"Returning tour_imgs collection: {self.tour_imgs_collection}")
    #     return self.tour_imgs_collection

    # def save_image_to_tour_imgs(self, filename, image_data, metadata=None):
    #     """Save an image to the tour_imgs collection with optional metadata."""
    #     try:
    #         collection = self.get_tour_imgs_collection()
    #         print(f"Collection accessible: {collection is not None}")
    #         if collection is None:
    #             print("Tour_imgs collection is None! Cannot save image.")
    #             return False
    #
    #         # Check if the image already exists
    #         existing = collection.find_one({"filename": filename})
    #         print(f"Checking for existing image {filename}: {existing is not None}")
    #         image_doc = {
    #             "filename": filename,
    #             "data": image_data,
    #             "metadata": metadata or {}
    #         }
    #         if existing:
    #             # Update existing image
    #             collection.update_one(
    #                 {"filename": filename},
    #                 {"$set": image_doc}
    #             )
    #             print(f"Updated image {filename} in tour_imgs collection.")
    #         else:
    #             # Insert new image
    #             collection.insert_one(image_doc)
    #             print(f"Saved image {filename} to tour_imgs collection.")
    #         return True
    #     except Exception as e:
    #         print(f"Error saving image {filename}: {e}")
    #         return False

    # def get_tour_image_by_filename(self, filename):
    #     """Retrieve an image from the tour_imgs collection by filename."""
    #     try:
    #         collection = self.get_tour_imgs_collection()
    #         if collection is None:
    #             raise ValueError("Tour_imgs collection is not initialized.")
    #         image_doc = collection.find_one({"filename": filename})
    #         if not image_doc:
    #             print(f"No image found with filename {filename}")
    #             return None
    #         return image_doc
    #     except Exception as e:
    #         print(f"Error retrieving image {filename}: {e}")
    #         return None

    # def is_tour_imgs_collection_empty(self):
    #     try:
    #         collection = self.get_tour_imgs_collection()
    #         if collection is None:
    #             raise ValueError("Tour_imgs collection is not initialized.")
    #         count = collection.count_documents({})
    #         print(f"Tour_imgs collection has {count} documents. Empty: {count == 0}")
    #         return count == 0
    #     except Exception as e:
    #         print(f"Error checking tour_imgs collection: {e}")
    #         return False

    def load_all_users(self):
        try:
            if self.users_collection is None:
                self.connect()
            self.all_users = list(self.users_collection.find())
            print(f"Loaded {len(self.all_users)} users from the database.")
        except Exception as e:
            print(f"Error loading users: {e}")
            self.all_users = []

    def get_users_collection(self):
        print("Getting users collection...")
        if self.users_collection is None:
            print("Users collection is None, connecting...")
            self.connect()
        print(f"Returning users collection: {self.users_collection}")
        return self.users_collection

    def get_tours_collection(self):
        print("Getting tours collection...")
        if self.tours_collection is None:
            print("Tours collection is None, connecting...")
            self.connect()
        print(f"Returning tours collection: {self.tours_collection}")
        return self.tours_collection

    def get_reviews_collection(self):
        print("Getting reviews collection...")
        if self.reviews_collection is None:
            print("Reviews collection is None, connecting...")
            self.connect()
        print(f"Returning reviews collection: {self.reviews_collection}")
        return self.reviews_collection

    def get_user_imgs_collection(self):
        print("Getting user_imgs collection...")
        if self.user_imgs_collection is None:
            print("User_imgs collection is None, connecting...")
            self.connect()
        print(f"Returning user_imgs collection: {self.user_imgs_collection}")
        return self.user_imgs_collection

    def save_image(self, filename, image_data):
        try:
            collection = self.get_user_imgs_collection()
            if collection.find_one({"filename": filename}):
                print(f"Image {filename} already exists in the database, skipping...")
                return False
            image_doc = {
                "filename": filename,
                "data": image_data
            }
            collection.insert_one(image_doc)
            print(f"Saved image {filename} to user_imgs collection.")
            return True
        except Exception as e:
            print(f"Error saving image {filename}: {e}")
            return False

    def is_user_imgs_collection_empty(self):
        try:
            collection = self.get_user_imgs_collection()
            if collection is None:
                raise ValueError("User_imgs collection is not initialized.")
            count = collection.count_documents({})
            print(f"User_imgs collection has {count} documents. Empty: {count == 0}")
            return count == 0
        except Exception as e:
            print(f"Error checking user_imgs collection: {e}")
            return False

    def get_all_users(self):
        if not self.all_users:
            self.load_all_users()
        return self.all_users

    def is_users_collection_empty(self):
        try:
            collection = self.get_users_collection()
            if collection is None:
                raise ValueError("Users collection is not initialized.")
            count = collection.count_documents({})
            print(f"Users collection has {count} documents. Empty: {count == 0}")
            return count == 0
        except Exception as e:
            print(f"Error checking users collection: {e}")
            return False

    def is_tours_collection_empty(self):
        try:
            collection = self.get_tours_collection()
            if collection is None:
                raise ValueError("Tours collection is not initialized.")
            count = collection.count_documents({})
            print(f"Tours collection has {count} documents. Empty: {count == 0}")
            return count == 0
        except Exception as e:
            print(f"Error checking tours collection: {e}")
            return False

    def is_reviews_collection_empty(self):
        try:
            collection = self.get_reviews_collection()
            if collection is None:
                raise ValueError("Reviews collection is not initialized.")
            count = collection.count_documents({})
            print(f"Reviews collection has {count} documents. Empty: {count == 0}")
            return count == 0
        except Exception as e:
            print(f"Error checking reviews collection: {e}")
            return False

    def debug_tours(self):
        try:
            count = self.tours_collection.count_documents({})
            non_secret_count = self.tours_collection.count_documents({"secret_tour": {"$ne": True}})
            print(f"Tours collection: {count} total, {non_secret_count} non-secret")
            tours = list(self.tours_collection.find())
            print("All tours:", tours)
            return count, non_secret_count, tours
        except Exception as e:
            print(f"Error debugging tours: {e}")
            return 0, 0, []

# Singleton instance
db = Database()