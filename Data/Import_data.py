import json
from db import db  # Import the singleton Database instance from db.py


class DataImporter:
    def __init__(self):
        print("Instantiating DataImporter...")
        # Access the collections from the db singleton
        self.users_collection = db.get_users_collection()
        self.tours_collection = db.get_tours_collection()
        self.reviews_collection = db.get_reviews_collection()

        # Verify that collections are initialized
        print("Verifying collections...")
        if self.users_collection is None:
            raise ValueError("Users collection is not initialized.")
        if self.tours_collection is None:
            raise ValueError("Tours collection is not initialized.")
        if self.reviews_collection is None:
            raise ValueError("Reviews collection is not initialized.")
        print("Collections verified successfully:")
        print(f"  Users collection: {self.users_collection}")
        print(f"  Tours collection: {self.tours_collection}")
        print(f"  Reviews collection: {self.reviews_collection}")

    def load_json_file(self, file_path):
        """Helper method to load data from a JSON file."""
        print(f"Loading JSON file: {file_path}")
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError(f"Expected a list of documents in {file_path}, but got {type(data)}")
            print(f"Loaded {len(data)} documents from {file_path}")
            return data
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            raise
        except json.JSONDecodeError:
            print(f"Error: The file '{file_path}' contains invalid JSON.")
            raise
        except Exception as e:
            print(f"Error loading JSON file '{file_path}': {e}")
            raise

    def rename_id_to_mongo_id(self, data):
        """Rename 'id' field to '_id' for MongoDB compatibility."""
        print("Renaming 'id' to '_id' in documents...")
        for doc in data:
            if 'id' in doc:
                doc['_id'] = doc.pop('id')
        return data

    def import_json_to_collection(self, file_path, collection, collection_name, is_collection_empty):
        """Import data from a JSON file into the specified MongoDB collection if the collection is empty."""
        print(f"Checking if '{collection_name}' collection is empty: {is_collection_empty}")
        if not is_collection_empty:
            print(f"'{collection_name}' collection is not empty. Skipping import from '{file_path}'.")
            return

        try:
            # Load the JSON data
            data = self.load_json_file(file_path)

            # Rename 'id' to '_id'
            data = self.rename_id_to_mongo_id(data)

            # Insert the data into the collection
            print(f"Inserting {len(data)} documents into '{collection_name}' collection...")
            result = collection.insert_many(data)
            print(
                f"Successfully inserted {len(result.inserted_ids)} documents into the '{collection_name}' collection.")
        except Exception as e:
            print(f"Error importing data from '{file_path}' into '{collection_name}' collection: {e}")
            raise

    def import_all_data(self, users_file='users.json', tours_file='tours.json', reviews_file='reviews.json'):
        """Import data from all JSON files into their respective collections, only if the collections are empty."""
        print("Starting data import process...")
        try:
            # Import users if the collection is empty
            print("Importing users...")
            self.import_json_to_collection(
                users_file,
                self.users_collection,
                'users',
                db.is_users_collection_empty()
            )

            # Import tours if the collection is empty
            print("Importing tours...")
            self.import_json_to_collection(
                tours_file,
                self.tours_collection,
                'tours',
                db.is_tours_collection_empty()
            )

            # Import reviews if the collection is empty
            print("Importing reviews...")
            self.import_json_to_collection(
                reviews_file,
                self.reviews_collection,
                'reviews',
                db.is_reviews_collection_empty()
            )

            # Reload users into memory after importing
            print("Reloading users into memory...")
            db.load_all_users()
            print("Data import process completed.")

        except Exception as e:
            print(f"Error during import_all_data: {e}")
            raise


# Example usage
if __name__ == "__main__":
    try:
        importer = DataImporter()
        importer.import_all_data(
            users_file='users.json',
            tours_file='tours.json',
            reviews_file='reviews.json'
        )
    except Exception as e:
        print(f"Failed to import data: {e}")