from flask import request, jsonify, g, send_file, render_template
from PIL import Image
import io
import os
import uuid

from mongoengine import ValidationError

from models.userModel import User, Role
from Utils.AppError import AppError
from Utils.apiFeature import APIFeatures
from functools import wraps
from bson import ObjectId
import logging
from datetime import datetime
from dateutil import parser
from db import db
from controllers.authController import create_send_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure upload settings (optional, will be used only temporarily if keeping filesystem storage)
UPLOAD_FOLDER = 'public/img/users'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Utility functions from handlerFactory
def camel_to_snake(name):
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper():
            if i > 0:
                result.append('_')
            result.append(char.lower())
        else:
            result.append(char)
    return ''.join(result)


def transform_data(data):
    """Transform camelCase keys to snake_case recursively."""
    if isinstance(data, dict):
        logger.debug(f"Transforming data: {data}")
        new_data = {}
        for key, value in data.items():
            new_key = camel_to_snake(key)
            if new_key == 'ratings_average':
                logger.debug(f"Found ratings_average (from {key})")
            elif new_key == 'rating_average':
                logger.debug(f"Found rating_average (from {key}), correcting to ratings_average")
                new_key = 'ratings_average'
            if new_key == 'start_dates' and isinstance(value, list):
                value = [parser.isoparse(date) if isinstance(date, str) else date for date in value]
            new_data[new_key] = transform_data(value)
        logger.debug(f"Transformed data: {new_data}")
        return new_data
    elif isinstance(data, list):
        return [transform_data(item) for item in data]
    else:
        return data


# Multer equivalent: Memory storage and filter
def multer_filter(file):
    allowed_mimetypes = [
        'image/png',
        'image/jpeg',
        'image/bmp',
        'image/tiff',
        'image/webp'
    ]
    if file and file.mimetype in allowed_mimetypes:
        return True
    if file and file.mimetype == 'image/gif':
        raise AppError('GIF files are not allowed. Please upload PNG, JPEG, BMP, TIFF, or WebP.', 400)
    raise AppError('Not a valid image! Please upload PNG, JPEG, BMP, TIFF, or WebP.', 400)


# Upload handler (replacing multer.single)
def upload_user_photo():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'photo' not in request.files:
                logger.debug("No photo uploaded in request")
                return f(*args, **kwargs)

            photo = request.files['photo']
            if not multer_filter(photo):
                logger.warning("Invalid photo uploaded")
                raise AppError('Invalid photo.', 400)

            request.file = photo
            logger.debug("Photo uploaded successfully")
            return f(*args, **kwargs)

        return wrapped

    return decorator


# Resize photo (replacing sharp)
def resize_user_photo():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                if not hasattr(request, 'file'):
                    logger.debug("No file to resize")
                    return f(*args, **kwargs)

                photo_file = request.file
                mime_type = photo_file.mimetype
                save_format = 'PNG' if mime_type == 'image/png' else 'JPEG'
                file_extension = 'png' if mime_type == 'image/png' else 'jpeg'
                filename = f"user-{g.user.id}-{uuid.uuid4().hex}.{file_extension}"

                photo = Image.open(photo_file)

                if photo.mode == 'RGBA' and save_format == 'JPEG':
                    photo = photo.convert('RGB')

                photo = photo.resize((500, 500), Image.Resampling.LANCZOS)

                img_byte_arr = io.BytesIO()
                photo.save(img_byte_arr, format=save_format, quality=90 if save_format == 'JPEG' else None)
                image_data = img_byte_arr.getvalue()

                success = db.save_image(filename, image_data)
                if not success:
                    logger.error(f"Failed to save image {filename} to user_imgs collection")
                    raise AppError("Failed to save image to database", 500)

                request.file_filename = filename
                logger.info(f"Photo resized and saved to tourist_db.user_imgs as {filename}")
                return f(*args, **kwargs)
            except AppError as e:
                raise e
            except Exception as e:
                logger.error(f"Error resizing photo: {str(e)}")
                raise AppError(f"Error processing photo: {str(e)}", 500)

        return wrapped

    return decorator


# Helper function to filter object fields
def filter_obj(obj, *allowed_fields):
    return {key: obj[key] for key in obj if key in allowed_fields}


# Middleware to set the current user's ID for /me routes
def set_current_user_id(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not hasattr(g, 'user'):
            logger.warning("User not authenticated in set_current_user_id")
            raise AppError('User not authenticated. Please log in.', 401)

        request.args = request.args.to_dict()
        request.args['id'] = str(g.user.id)
        logger.debug(f"Set request.args['id'] to {g.user.id} for /me route")
        return f(*args, **kwargs)

    return wrapped


# Format the current user's data
def get_current_user_data():
    if not hasattr(g, 'user'):
        logger.warning("Attempt to get current user data without authenticated user")
        raise AppError('You must be logged in to access this resource', 401)

    user = g.user
    logger.debug(f"Formatting user data for: {user.email}")
    photo_url = f"/api/v1/users/image/{str(user.id)}" if user.photo else None
    return jsonify({
        "status": "success",
        "data": {
            "data": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "photo": photo_url,
                "location": getattr(user, 'location', None),
                "profile_slug": user.profile_slug  # Add profile_slug
            }
        }
    }), 200

# New handler to check if an email exists
def check_email():
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            raise AppError("Email is required", 400)

        email = data['email']
        logger.debug(f"Checking email availability: {email}")

        user = User.objects(email=email).first()
        exists = user is not None

        return jsonify({
            "status": "success",
            "exists": exists
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in check_email: {str(e)}")
        raise AppError(str(e), 500)


# User-specific handlers
def get_all_users():
    try:
        query = User.objects()
        query_string = getattr(request, 'modified_args', None) or request.args.to_dict()
        logger.debug(f"Query string: {query_string}")
        features = APIFeatures(query, query_string)
        features = features.filter()
        features = features.sort()
        features = features.limit_fields()
        features = features.paginate()
        docs = list(features.query)

        logger.debug(f"Final users count: {len(docs)}")
        return jsonify({
            "status": "success",
            "results": len(docs),
            "data": {
                "data": [
                    {
                        "id": str(doc.id),
                        "email": doc.email,
                        "name": doc.name,
                        "photo": f"/api/v1/users/image/{str(doc.id)}" if doc.photo else None,
                        "role": doc.role,
                        "active": doc.active,
                        "location": getattr(doc, 'location', None)
                    } for doc in docs
                ]
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_all_users: {str(e)}")
        raise AppError(str(e), 500)


def get_one_user(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        logger.debug(f"Converted ObjectId: {object_id} (type: {type(object_id)})")
        logger.debug(f"Querying collection: {User._get_collection().name}")

        doc = User.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No user found with that ID', 404)
        logger.debug(f"Found user: {doc.to_json()}")

        user_data = {
            "id": str(doc.id),
            "email": doc.email,
            "name": doc.name,
            "photo": f"/api/v1/users/image/{str(doc.id)}" if doc.photo else None,
            "role": doc.role,
            "active": doc.active,
            "location": getattr(doc, 'location', None)
        }
        return jsonify({
            "status": "success",
            "data": {
                "data": user_data
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_user: {str(e)}")
        raise AppError(str(e), 500)


# In userController.py
def create_one_user():
    try:
        data = request.get_json()
        if not data:
            raise AppError("Request body is required", 400)

        logger.debug(f"Incoming create data: {data}")
        data = transform_data(data)
        logger.debug(f"Transformed create data: {data}")

        # Validate required fields
        required_fields = ['name', 'email', 'password', 'password_confirm']
        for field in required_fields:
            if field not in data or not data[field]:
                raise AppError(f"{field} is required", 400)

        # Validate password confirmation
        if data['password'] != data['password_confirm']:
            raise AppError("Passwords do not match", 400)

        # Validate password length
        if len(data['password']) < 8:
            raise AppError("Password must be at least 8 characters long", 400)

        # Validate name length
        if len(data['name']) < 2:
            raise AppError("Name must be at least 2 characters long", 400)

        # Remove password_confirm from data since it's not a field in the model
        data.pop('password_confirm', None)

        # Remove profile_slug if provided (let model generate it)
        data.pop('profile_slug', None)

        # Set default role if not provided
        if 'role' not in data:
            data['role'] = Role.USER

        doc = User(**data)
        doc.save()
        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 201
    except ValidationError as e:
        logger.error(f"Validation error in create_one_user: {str(e)}")
        raise AppError(str(e), 400)
    except Exception as e:
        logger.error(f"Error in create_one_user: {str(e)}")
        raise AppError(str(e), 500)


def update_one_user(id):
    try:
        data = request.get_json()
        if not data:
            raise AppError("No data provided for update", 400)
        data = transform_data(data)
        logger.debug(f"Transformed update data: {data}")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = User.objects(id=object_id).first()
        if not doc:
            raise AppError('No user found with that ID', 404)
        doc.update(**data)
        updated_doc = User.objects(id=object_id).first()
        return jsonify({
            "status": "success",
            "data": {
                "data": updated_doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in update_one_user: {str(e)}")
        raise AppError(str(e), 500)


def delete_one_user(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = User.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No user found with that ID', 404)

        doc.delete()
        logger.debug(f"Deleted user with ID: {id}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_one_user: {str(e)}")
        raise AppError(str(e), 500)


# Enhanced update_me to handle dashboard updates
@upload_user_photo()
@resize_user_photo()
def update_me():
    try:
        data = {}
        if request.form:
            data.update(request.form.to_dict())
        logger.debug(f"Received form data: {data}")

        if 'password_confirm' in data:
            logger.warning("Attempt to update passwordConfirm via update_me")
            raise AppError('This route does not support passwordConfirm. Please use /updateMyPassword.', 400)

        filtered_body = {}
        allowed_fields = ('name', 'email', 'location', 'password')
        for field in allowed_fields:
            if field in data and data[field] and data[field].strip():
                filtered_body[field] = data[field].strip()

        if 'name' not in filtered_body or not filtered_body['name']:
            logger.warning("Name is missing or empty")
            raise AppError('Name is required and must be at least 2 characters long.', 400)
        if len(filtered_body['name']) < 2:
            logger.warning(f"Name too short: {filtered_body['name']}")
            raise AppError('Name must be at least 2 characters long.', 400)

        if 'password' in filtered_body and len(filtered_body['password']) < 6:
            logger.warning(f"Password too short: {filtered_body['password']}")
            raise AppError('Password must be at least 6 characters long.', 400)

        if hasattr(request, 'file_filename'):
            filtered_body['photo'] = request.file_filename
            logger.debug(f"Photo included: {filtered_body['photo']}")

        if 'password' in filtered_body:
            user = User.objects(id=g.user.id).first()
            if not user:
                logger.warning(f"No user found with ID {g.user.id}")
                raise AppError('No user found with that ID', 404)
            user.password = filtered_body['password']
            user.save()
            del filtered_body['password']
            logger.debug("Password updated")

        if not hasattr(g, 'user'):
            logger.warning("User not authenticated in update_me")
            raise AppError('User not authenticated', 401)
        user = User.objects(id=g.user.id).first()
        if not user:
            logger.warning(f"No user found with ID {g.user.id}")
            raise AppError('No user found with that ID', 404)

        if filtered_body:
            user.update(**filtered_body)
            logger.debug(f"Updated fields: {filtered_body}")

        updated_user = User.objects(id=g.user.id).first()

        logger.info(f"User updated successfully: {updated_user.email}")
        return create_send_token(updated_user, 200)
        #return jsonify({
        #    "message": "Profile updated successfully",
        #    "data": {"user": updated_user.to_json()}
        #}), 200 
    except AppError as e:
        logger.error(f"AppError: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating user: {str(e)}")
        raise AppError(f"Error updating user: {str(e)}", 500)


def delete_me():
    try:
        if not hasattr(g, 'user'):
            logger.warning("User not authenticated in delete_me")
            raise AppError('User not authenticated', 401)
        user = User.objects(id=g.user.id).first()
        if not user:
            logger.warning(f"No user found with ID {g.user.id}")
            raise AppError('No user found with that ID', 404)
        user.update(active=False)
        logger.info(f"User deactivated: {user.email}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error deactivating user: {str(e)}")
        raise AppError(f"Error deactivating user: {str(e)}", 500)


def create_user():
    logger.warning("Attempt to use create_user route")
    return jsonify({
        "status": "error",
        "message": "This route is not defined! Please use /signup instead"
    }), 500


def serve_user_image(profile_slug):  # Change parameter to profile_slug
    try:
        user = User.objects(profile_slug=profile_slug).first()
        if not user:
            raise AppError(f"User with profile slug {profile_slug} not found", 404)

        if not user.photo:
            raise AppError(f"User {profile_slug} has no photo", 404)

        photo_filename = user.photo
        logger.debug(f"Photo filename for user {profile_slug}: {photo_filename}")

        collection = db.get_user_imgs_collection()
        image_doc = collection.find_one({"filename": photo_filename})
        if not image_doc:
            raise AppError(f"Image {photo_filename} not found in user_imgs collection", 404)

        image_data = image_doc['data']
        if not isinstance(image_data, bytes):
            raise AppError(f"Image data for {photo_filename} is not in binary format", 500)

        image = Image.open(io.BytesIO(image_data))
        file_extension = photo_filename.split('.')[-1].lower()
        save_format = 'PNG' if file_extension == 'png' else 'JPEG'
        mime_type = 'image/png' if file_extension == 'png' else 'image/jpeg'

        if image.mode == 'RGBA' and save_format == 'JPEG':
            image = image.convert('RGB')

        width, height = image.size
        target_size = 142

        if width < target_size or height < target_size:
            logger.debug(
                f"Image for user {profile_slug} is too small ({width}x{height}). Resizing to {target_size}x{target_size}.")
            image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)
        elif width > target_size or height > target_size:
            logger.debug(
                f"Image for user {profile_slug} is too large ({width}x{height}). Resizing to {target_size}x{target_size}.")
            image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)

        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=save_format, quality=90 if save_format == 'JPEG' else None)
        resized_image_data = img_byte_arr.getvalue()

        logger.info(f"Successfully serving image for user {profile_slug}")
        return send_file(
            io.BytesIO(resized_image_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=photo_filename
        )
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error serving image for user {profile_slug}: {str(e)}")
        raise AppError(f"Error serving image for user {profile_slug}: {str(e)}", 500)

# New Dashboard Handler
def dashboard(user_id):
    try:
        # Ensure the user is authenticated
        if not hasattr(g, 'user'):
            logger.warning("User not authenticated in dashboard")
            raise AppError('User not authenticated. Please log in.', 401)

        # Validate user_id against the authenticated user
        if str(g.user.id) != user_id:
            logger.warning(f"Authenticated user {g.user.id} attempted to access dashboard for user {user_id}")
            raise AppError("Unauthorized access", 403)

        # Fetch the user from the database
        user = User.objects(id=user_id).first()
        if not user:
            logger.warning(f"No user found with ID {user_id}")
            raise AppError("User not found", 404)

        # Prepare user data for the template
        user_data = {
            'id': str(user.id),
            'email': user.email,
            'name': user.name,
            'photo': user.photo or '/img/users/default.jpg',  # Fallback for photo
            'location': getattr(user, 'location', '')
        }

        logger.info(f"Rendering dashboard for user: {user.email}")
        return render_template('dashboard.html', user=user_data)
    except AppError as e:
        logger.error(f"AppError in dashboard: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error rendering dashboard for user {user_id}: {str(e)}")
        raise AppError(f"Error rendering dashboard: {str(e)}", 500)

def upload_image_to_imgs():
    try:
        if not hasattr(request, 'file'):
            logger.warning("No image file provided in request")
            raise AppError("No image file provided", 400)

        image_file = request.file
        mime_type = image_file.mimetype
        file_extension = 'png' if mime_type == 'image/png' else 'jpeg'
        # Use the original filename if provided, else generate a unique one
        original_filename = image_file.filename
        filename = original_filename if original_filename and original_filename.lower().endswith(('.jpg', '.jpeg', '.png')) else f"img-{uuid.uuid4().hex}.{file_extension}"
        logger.debug(f"Using filename: {filename}")

        # Read the image data
        image_data = image_file.read()
        if not image_data:
            logger.warning("Empty image file provided")
            raise AppError("Image file is empty", 400)

        # Save to imgs collection
        success = db.save_image_to_imgs(filename, image_data)
        if not success:
            logger.error(f"Failed to save image {filename} to imgs collection")
            raise AppError("Failed to save image to database", 500)

        logger.info(f"Image {filename} saved to tourist_db.imgs")
        return jsonify({
            "status": "success",
            "message": "Image uploaded successfully",
            "data": {
                "filename": filename
            }
        }), 201
    except AppError as e:
        logger.error(f"AppError in upload_image_to_imgs: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in upload_image_to_imgs: {str(e)}")
        raise AppError(f"Error uploading image: {str(e)}", 500)

# Route handlers
get_all_users = get_all_users
get_user = get_one_user
update_user = update_one_user
delete_user = delete_one_user
check_email = check_email
upload_image_to_imgs = upload_image_to_imgs