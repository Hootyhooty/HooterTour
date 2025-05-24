from flask import request, jsonify, g
from models.reviewModel import Review
from models.tourModel import Tour
from models.userModel import User
from Utils.AppError import AppError
from Utils.apiFeature import APIFeatures
from bson import ObjectId
import logging
from datetime import datetime
from dateutil import parser

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

# Middleware to set tour and user IDs
def set_tour_user_ids():
    def wrapper(f):
        def decorated(*args, **kwargs):
            data = request.get_json() if request.method in ['POST', 'PATCH'] else {}
            if request.method == 'POST':
                if 'tour' not in data and 'tourId' in request.args:
                    tour_id = request.args.get('tourId')
                    try:
                        tour = Tour.objects(id=tour_id).first()
                        if not tour:
                            logger.warning(f"Tour not found for tourId: {tour_id}")
                            raise AppError("Tour not found with the provided tourId", 404)
                        data['tour'] = tour_id
                    except Exception as e:
                        logger.error(f"Invalid tourId format: {tour_id}, error: {str(e)}")
                        raise AppError("Invalid tourId format", 400)
                if 'user' not in data and hasattr(g, 'user'):
                    data['user'] = str(g.user.id)
            g.modified_data = data
            logger.debug(f"Set tour and user IDs: {data}")
            return f(*args, **kwargs)
        return decorated
    return wrapper

# Review-specific handlers
def get_all_reviews():
    try:
        filter_kwargs = {}
        if 'tourId' in request.args:
            tour_id = request.args.get('tourId')
            try:
                tour = Tour.objects(id=tour_id).first()
                if not tour:
                    logger.warning(f"Tour not found for tourId: {tour_id}")
                    raise AppError("Tour not found with the provided tourId", 404)
                filter_kwargs['tour'] = tour_id
            except Exception as e:
                logger.error(f"Invalid tourId format: {tour_id}, error: {str(e)}")
                raise AppError("Invalid tourId format", 400)

        query = Review.objects(__raw__={**filter_kwargs})
        logger.debug(f"Collection name for Review: {Review._get_collection().name}")
        query_string = getattr(request, 'modified_args', None) or request.args.to_dict()
        logger.debug(f"Query string: {query_string}")
        features = APIFeatures(query, query_string)
        features = features.filter()
        logger.debug(f"After filter: {features.query.count()}")
        features = features.sort()
        logger.debug(f"After sort: {features.query.count()}")
        features = features.limit_fields()
        logger.debug(f"After limit_fields: {features.query.count()}")
        features = features.paginate()
        logger.debug(f"After paginate: {features.query.count()}")
        docs = list(features.query)

        logger.debug(f"Final reviews count: {len(docs)}")
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
        logger.error(f"Error in get_all_reviews: {str(e)}")
        raise AppError(str(e), 500)

def get_one_review(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        logger.debug(f"Converted ObjectId: {object_id} (type: {type(object_id)})")
        logger.debug(f"Querying collection: {Review._get_collection().name}")

        doc = Review.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No review found with that ID', 404)
        logger.debug(f"Found review: {doc.to_json()}")

        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_review: {str(e)}")
        raise AppError(str(e), 500)

def create_one_review():
    try:
        data = g.modified_data if hasattr(g, 'modified_data') else request.get_json()
        logger.debug(f"Incoming create data: {data}")
        data = transform_data(data)
        logger.debug(f"Transformed create data: {data}")

        if 'tour' not in data:
            raise AppError("Tour ID is required", 400)
        try:
            tour_id = ObjectId(data['tour'])
        except Exception as e:
            logger.error(f"Invalid tour ID format: {data['tour']}, error: {str(e)}")
            raise AppError("Invalid tour ID format", 400)
        tour = Tour.objects(id=tour_id).first()
        if not tour:
            logger.warning(f"Tour not found for ID: {tour_id}")
            raise AppError("Tour not found with the provided ID", 404)

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

        existing_review = Review.objects(tour=tour_id, user=user_id).first()
        if existing_review:
            logger.warning(f"Review already exists for tour {tour_id} and user {user_id}")
            raise AppError("A review for this tour by this user already exists", 409)

        doc = Review(**data)
        doc.save()
        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 201
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in create_one_review: {str(e)}")
        raise AppError(str(e), 500)

def update_one_review(id):
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

        doc = Review.objects(id=object_id).first()
        if not doc:
            raise AppError('No review found with that ID', 404)

        # Only perform duplicate check if tour or user is being updated
        check_duplicate = False
        tour_id = doc.tour.id  # Default to existing tour ID
        user_id = doc.user.id  # Default to existing user ID

        if 'tour' in data:
            try:
                tour_id = ObjectId(data['tour'])
            except Exception as e:
                logger.error(f"Invalid tour ID format: {data['tour']}, error: {str(e)}")
                raise AppError("Invalid tour ID format", 400)
            tour = Tour.objects(id=tour_id).first()
            if not tour:
                logger.warning(f"Tour not found for ID: {tour_id}")
                raise AppError("Tour not found with the provided ID", 404)
            data['tour'] = tour_id
            check_duplicate = True

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

        logger.debug(f"check_duplicate: {check_duplicate}, tour_id: {tour_id}, user_id: {user_id}")
        if check_duplicate:
            existing_review = Review.objects(tour=tour_id, user=user_id, id__ne=object_id).first()
            if existing_review:
                logger.warning(f"Review already exists for tour {tour_id} and user {user_id} with ID {existing_review.id}")
                raise AppError("A review for this tour by this user already exists", 409)

        doc.update(**data)
        updated_doc = Review.objects(id=object_id).first()
        return jsonify({
            "status": "success",
            "data": {
                "data": updated_doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in update_one_review: {str(e)}")
        raise AppError(str(e), 500)

def delete_one_review(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = Review.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No review found with that ID', 404)

        # Check if the current user is the review's author or an admin
        if not hasattr(g, 'user'):
            logger.warning("Delete attempt without authenticated user")
            raise AppError("You must be logged in to perform this action", 401)

        current_user_id = str(g.user.id)
        review_author_id = str(doc.user.id)
        is_admin = g.user.role.value == 'admin'

        logger.debug(f"Current user ID: {current_user_id}, Review author ID: {review_author_id}, Is admin: {is_admin}")
        if current_user_id != review_author_id and not is_admin:
            logger.warning(f"User {current_user_id} attempted to delete review {id} but is neither the author nor an admin")
            raise AppError("You can only delete your own reviews unless you are an admin", 403)

        doc.delete()
        logger.debug(f"Deleted review with ID: {id}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_one_review: {str(e)}")
        raise AppError(str(e), 500)

# Route handlers
get_all_reviews = get_all_reviews
get_review = get_one_review
create_review = set_tour_user_ids()(create_one_review)
update_review = set_tour_user_ids()(update_one_review)
delete_review = set_tour_user_ids()(delete_one_review)