from datetime import datetime

from flask import request, jsonify, g
from models.testimonialModel import Testimonial
from models.userModel import User
from Utils.AppError import AppError
from Utils.apiFeature import APIFeatures
from bson import ObjectId
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Utility functions
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
            new_data[new_key] = transform_data(value)
        logger.debug(f"Transformed data: {new_data}")
        return new_data
    elif isinstance(data, list):
        return [transform_data(item) for item in data]
    else:
        return data


# Middleware to set user ID and name
def set_user_id_and_name():
    def wrapper(f):
        def decorated(*args, **kwargs):
            data = request.get_json() if request.method in ['POST', 'PATCH'] else {}
            if request.method == 'POST':
                if 'user' not in data and hasattr(g, 'user'):
                    data['user'] = str(g.user.id)
                    data['name'] = g.user.name  # Set name from logged-in user
            g.modified_data = data
            logger.debug(f"Set user ID and name: {data}")
            return f(*args, **kwargs)

        return decorated

    return wrapper


# Testimonial-specific handlers
def get_all_testimonials():
    try:
        query = Testimonial.objects(__raw__={})
        query_string = getattr(request, 'modified_args', None) or request.args.to_dict()
        features = APIFeatures(query, query_string)
        features = features.filter().sort().limit_fields().paginate()
        docs = list(features.query)

        # Populate user data for each testimonial
        docs = [doc.populate() for doc in docs]

        return jsonify({
            "status": "success",
            "results": len(docs),
            "data": {
                "data": [doc.to_json() for doc in docs]
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_all_testimonials: {str(e)}")
        raise AppError(str(e), 500)

def get_one_testimonial(id):
    try:
        try:
            object_id = ObjectId(id)
        except Exception as e:
            raise AppError("Invalid ID format", 400)

        doc = Testimonial.objects(id=object_id).first()
        if not doc:
            raise AppError('No testimonial found with that ID', 404)

        # Populate user data
        doc = doc.populate()

        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_testimonial: {str(e)}")
        raise AppError(str(e), 500)

def create_one_testimonial():
    try:
        data = g.modified_data if hasattr(g, 'modified_data') else request.get_json()
        logger.debug(f"Incoming create data: {data}")
        data = transform_data(data)
        logger.debug(f"Transformed create data: {data}")

        if 'user' not in data:
            raise AppError("User ID is required", 400)
        try:
            user_id = ObjectId(data['user'])
        except Exception as e:
            logger.error(f"Invalid user ID format: {data['user']}, error: {str(e)}")
            raise AppError("Invalid user ID format", 400)
        user = User.objects(id=user_id).first()
        if not user:
            logger.warning(f"User not found for ID: {user_id}")
            raise AppError("User not found with the provided ID", 404)

        if 'name' not in data:
            raise AppError("Name is required", 400)
        if data['name'] != user.name:
            logger.warning(f"Provided name {data['name']} does not match user name {user.name}")
            raise AppError("Name must match the authenticated user's name", 400)

        # Check for existing testimonial by the same user
        existing_testimonial = Testimonial.objects(user=user_id).first()
        if existing_testimonial:
            logger.info(f"Replacing existing testimonial for user {user_id}")
            existing_testimonial.update(
                review=data['review'],
                name=data['name'],
                date=datetime.utcnow()  # Update the date to reflect the new testimonial
            )
            updated_doc = Testimonial.objects(id=existing_testimonial.id).first()
            updated_doc = updated_doc.populate()  # Populate user data for response
            return jsonify({
                "status": "success",
                "data": {
                    "data": updated_doc.to_json()
                }
            }), 200  # Return 200 for update instead of 201
        else:
            # Create new testimonial if none exists
            doc = Testimonial(**data)
            doc.save()
            doc = doc.populate()  # Populate user data for response
            return jsonify({
                "status": "success",
                "data": {
                    "data": doc.to_json()
                }
            }), 201

    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in create_one_testimonial: {str(e)}")
        raise AppError(str(e), 500)


def update_one_testimonial(id):
    try:
        data = g.modified_data if hasattr(g, 'modified_data') else request.get_json()
        if not data:
            raise AppError("No data provided for update", 400)
        data = transform_data(data)
        logger.debug(f"Transformed update data: {data}")

        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = Testimonial.objects(id=object_id).first()
        if not doc:
            raise AppError('No testimonial found with that ID', 404)

        # Check if user is being updated
        check_duplicate = False
        user_id = doc.user.id  # Default to existing user ID

        if 'user' in data:
            try:
                user_id = ObjectId(data['user'])
            except Exception as e:
                logger.error(f"Invalid user ID format: {data['user']}, error: {str(e)}")
                raise AppError("Invalid user ID format", 400)
            user = User.objects(id=user_id).first()
            if not user:
                logger.warning(f"User not found for ID: {user_id}")
                raise AppError("User not found with the provided ID", 404)
            data['user'] = user_id
            check_duplicate = True

        if 'name' in data:
            user = User.objects(id=user_id).first()
            if data['name'] != user.name:
                logger.warning(f"Provided name {data['name']} does not match user name {user.name}")
                raise AppError("Name must match the authenticated user's name", 400)

        logger.debug(f"check_duplicate: {check_duplicate}, user_id: {user_id}")
        if check_duplicate:
            existing_testimonial = Testimonial.objects(user=user_id, id__ne=object_id).first()
            if existing_testimonial:
                logger.warning(f"Testimonial already exists for user {user_id} with ID {existing_testimonial.id}")
                raise AppError("A testimonial by this user already exists", 409)

        doc.update(**data)
        updated_doc = Testimonial.objects(id=object_id).first()
        updated_doc = updated_doc.populate()  # Populate user data for response
        return jsonify({
            "status": "success",
            "data": {
                "data": updated_doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in update_one_testimonial: {str(e)}")
        raise AppError(str(e), 500)


def delete_one_testimonial(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = Testimonial.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No testimonial found with that ID', 404)

        # Check if the current user is the testimonial's author or an admin
        if not hasattr(g, 'user'):
            logger.warning("Delete attempt without authenticated user")
            raise AppError("You must be logged in to perform this action", 401)

        current_user_id = str(g.user.id)
        testimonial_author_id = str(doc.user.id)
        is_admin = g.user.role.value == 'admin'

        logger.debug(
            f"Current user ID: {current_user_id}, Testimonial author ID: {testimonial_author_id}, Is admin: {is_admin}")
        if current_user_id != testimonial_author_id and not is_admin:
            logger.warning(
                f"User {current_user_id} attempted to delete testimonial {id} but is neither the author nor an admin")
            raise AppError("You can only delete your own testimonials unless you are an admin", 403)

        doc.delete()
        logger.debug(f"Deleted testimonial with ID: {id}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_one_testimonial: {str(e)}")
        raise AppError(str(e), 500)


# Route handlers
get_all_testimonials = get_all_testimonials
get_testimonial = get_one_testimonial
create_testimonial = set_user_id_and_name()(create_one_testimonial)
update_testimonial = set_user_id_and_name()(update_one_testimonial)
delete_testimonial = set_user_id_and_name()(delete_one_testimonial)