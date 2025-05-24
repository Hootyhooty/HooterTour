import traceback

from flask import request, jsonify
from PIL import Image
import os
from models.tourModel import Tour
from models.reviewModel import Review
from Utils.AppError import AppError
from Utils.apiFeature import APIFeatures
import uuid
from functools import wraps
from bson import ObjectId
import logging
from datetime import datetime
from dateutil import parser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure upload settings
UPLOAD_FOLDER = 'public/img/tours'
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
    if file and file.mimetype.startswith('image'):
        return True
    logger.warning("Invalid file type uploaded: not an image")
    raise AppError('Not an image! Please upload only images.', 400)


# Upload handler (replacing multer.fields)
def upload_tour_images():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'imageCover' not in request.files or 'images' not in request.files:
                logger.debug("No imageCover or images in request.files")
                return f(*args, **kwargs)

            image_cover = request.files.getlist('imageCover')
            images = request.files.getlist('images')

            if not image_cover or not multer_filter(image_cover[0]):
                logger.warning("Invalid cover image uploaded")
                raise AppError('Invalid cover image.', 400)
            if not all(multer_filter(img) for img in images):
                logger.warning("Invalid images uploaded")
                raise AppError('Invalid images.', 400)

            request.files_dict = {
                'imageCover': image_cover[0],
                'images': images
            }
            logger.debug("Tour images uploaded successfully")
            return f(*args, **kwargs)

        return wrapped

    return decorator


# Resize images (replacing sharp)
def resize_tour_images():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                if not hasattr(request, 'files_dict') or not request.files_dict.get(
                        'imageCover') or not request.files_dict.get('images'):
                    logger.debug("No images to resize")
                    return f(*args, **kwargs)

                tour_id = request.args.get('id') or (request.json or {}).get('id')
                if not tour_id:
                    logger.warning("No tour ID provided for image resizing")
                    raise AppError('Tour ID is required for image uploads.', 400)

                image_cover_file = request.files_dict['imageCover']
                filename_cover = f"tour-{tour_id}-{uuid.uuid4().hex}-cover.jpeg"
                image_cover = Image.open(image_cover_file)
                image_cover = image_cover.resize((2000, 1333), Image.Resampling.LANCZOS)
                image_cover.save(os.path.join(UPLOAD_FOLDER, filename_cover), 'JPEG', quality=90)

                images_filenames = []
                for i, image_file in enumerate(request.files_dict['images']):
                    filename = f"tour-{tour_id}-{uuid.uuid4().hex}-{i + 1}.jpeg"
                    image = Image.open(image_file)
                    image = image.resize((2000, 1333), Image.Resampling.LANCZOS)
                    image.save(os.path.join(UPLOAD_FOLDER, filename), 'JPEG', quality=90)
                    images_filenames.append(filename)

                request.json = request.json or {}
                request.json['imageCover'] = filename_cover
                request.json['images'] = images_filenames

                logger.info(f"Resized and saved tour images: {filename_cover}, {images_filenames}")
                return f(*args, **kwargs)
            except AppError as e:
                raise e
            except Exception as e:
                logger.error(f"Error resizing tour images: {str(e)}")
                raise AppError(f"Error processing tour images: {str(e)}", 500)

        return wrapped

    return decorator


# Middleware to alias top tours
def alias_top_tours():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            logger.debug("Applying alias_top_tours decorator")
            modified_args = request.args.to_dict()
            modified_args['limit'] = '5'
            modified_args['sort'] = '-ratings_average,price'
            modified_args['fields'] = 'name,price,ratings_average,summary,difficulty'
            request.modified_args = modified_args
            logger.debug(f"Modified query args: {modified_args}")
            return f(*args, **kwargs)

        return wrapped

    return decorator


# Tour-specific handlers (moved from handlerFactory)
def get_all_tours():
    try:
        filter_kwargs = {}
        if 'tourId' in request.args:
            filter_kwargs['tour'] = request.args.get('tourId')

        query = Tour.objects(__raw__={**filter_kwargs})
        logger.debug(f"Collection name for Tour: {Tour._get_collection().name}")
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

        logger.debug(f"Final tours count: {len(docs)}")
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
        logger.error(f"Error in get_all_tours: {str(e)}")
        raise AppError(str(e), 500)


def get_one_tour(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        logger.debug(f"Converted ObjectId: {object_id} (type: {type(object_id)})")
        logger.debug(f"Querying collection: {Tour._get_collection().name}")

        doc = Tour.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No tour found with that ID', 404)
        logger.debug(f"Found tour: {doc.to_json()}")

        if hasattr(doc, 'populate'):
            doc = doc.populate(path='reviews')

        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_tour: {str(e)}")
        raise AppError(str(e), 500)


def create_one_tour():
    try:
        data = request.get_json()
        logger.debug(f"Incoming create data: {data}")
        data = transform_data(data)
        logger.debug(f"Transformed create data: {data}")
        doc = Tour(**data)
        doc.save()
        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 201
    except Exception as e:
        logger.error(f"Error in create_one_tour: {str(e)}")
        raise AppError(str(e), 500)


def update_one_tour(id):
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

        doc = Tour.objects(id=object_id).first()
        if not doc:
            raise AppError('No tour found with that ID', 404)
        doc.update(**data)
        updated_doc = Tour.objects(id=object_id).first()
        return jsonify({
            "status": "success",
            "data": {
                "data": updated_doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in update_one_tour: {str(e)}")
        raise AppError(str(e), 500)


def delete_one_tour(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = Tour.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No tour found with that ID', 404)

        doc.delete()
        logger.debug(f"Deleted tour with ID: {id}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_one_tour: {str(e)}")
        raise AppError(str(e), 500)


# Custom handlers (unchanged)
def get_tour_stats():
    try:
        stats = Tour.objects.aggregate([
            {"$match": {"ratings_average": {"$gte": 4.5}}},
            {"$group": {
                "_id": {"$toUpper": "$difficulty"},
                "numTours": {"$sum": 1},
                "numRatings": {"$sum": "$ratings_quantity"},
                "avgRating": {"$avg": "$ratings_average"},
                "avgPrice": {"$avg": "$price"},
                "minPrice": {"$min": "$price"},
                "maxPrice": {"$max": "$price"}
            }},
            {"$sort": {"avgPrice": 1}}
        ])
        logger.info("Retrieved tour statistics")
        return jsonify({
            "status": "success",
            "data": {"stats": list(stats)}
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tour stats: {str(e)}")
        raise AppError(f"Error retrieving tour stats: {str(e)}", 500)


def get_monthly_plan():
    try:
        year = request.args.get('year', 2021)
        try:
            year = int(year)
            if year < 2000 or year > 2100:
                raise ValueError("Year must be between 2000 and 2100")
        except ValueError as e:
            logger.warning(f"Invalid year provided: {year}")
            raise AppError(f"Invalid year: {str(e)}", 400)

        plan = Tour.objects.aggregate([
            {"$unwind": "$start_dates"},
            {"$match": {
                "start_dates": {
                    "$gte": {"$date": f"{year}-01-01T00:00:00Z"},
                    "$lte": {"$date": f"{year}-12-31T23:59:59Z"}
                }
            }},
            {"$group": {
                "_id": {"$month": "$start_dates"},
                "numTourStarts": {"$sum": 1},
                "tours": {"$push": "$name"}
            }},
            {"$addFields": {"month": "$_id"}},
            {"$project": {"_id": 0}},
            {"$sort": {"numTourStarts": -1}},
            {"$limit": 12}
        ])
        logger.info(f"Retrieved monthly plan for year {year}")
        return jsonify({
            "status": "success",
            "data": {"plan": list(plan)}
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving monthly plan: {str(e)}")
        raise AppError(f"Error retrieving monthly plan: {str(e)}", 500)


def get_tours_within():
    try:
        distance = request.args.get('distance')
        latlng = request.args.get('latlng')
        unit = request.args.get('unit', 'km')

        if not distance or not latlng:
            logger.warning("Missing distance or latlng parameters")
            raise AppError('Please provide distance and latlng in the format lat,lng.', 400)

        try:
            distance = float(distance)
            if distance <= 0:
                raise ValueError("Distance must be a positive number")
        except ValueError as e:
            logger.warning(f"Invalid distance provided: {distance}")
            raise AppError(f"Invalid distance: {str(e)}", 400)

        try:
            lat, lng = map(float, latlng.split(','))
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise ValueError("Latitude must be between -90 and 90, longitude between -180 and 180")
        except ValueError as e:
            logger.warning(f"Invalid latlng provided: {latlng}")
            raise AppError(f"Invalid latlng: {str(e)}", 400)

        radius = distance / 6378.1 if unit == 'km' else distance / 3963.2

        tours = Tour.objects(__raw__={
            "start_location": {
                "$geoWithin": {
                    "$centerSphere": [[lng, lat], radius]
                }
            }
        })
        logger.info(f"Retrieved {tours.count()} tours within {distance} {unit} of ({lat}, {lng})")
        return jsonify({
            "status": "success",
            "results": tours.count(),
            "data": {"data": [tour.to_json() for tour in tours]}
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tours within distance: {str(e)}")
        raise AppError(f"Error retrieving tours within distance: {str(e)}", 500)


def get_distances():
    try:
        latlng = request.args.get('latlng')
        unit = request.args.get('unit', 'km')

        if not latlng:
            logger.warning("Missing latlng parameter")
            raise AppError('Please provide latitude and longitude in the format lat,lng.', 400)

        try:
            lat, lng = map(float, latlng.split(','))
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise ValueError("Latitude must be between -90 and 90, longitude between -180 and 180")
        except ValueError as e:
            logger.warning(f"Invalid latlng provided: {latlng}")
            raise AppError(f"Invalid latlng: {str(e)}", 400)

        multiplier = 0.001 if unit == 'km' else 0.000621371

        distances = Tour.objects.aggregate([
            {"$geoNear": {
                "near": {"type": "Point", "coordinates": [lng, lat]},
                "distanceField": "distance",
                "distanceMultiplier": multiplier
            }},
            {"$project": {"distance": 1, "name": 1}}
        ])
        logger.info(f"Retrieved distances for tours from ({lat}, {lng}) in {unit}")
        return jsonify({
            "status": "success",
            "data": {"data": list(distances)}
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tour distances: {str(e)}")
        raise AppError(f"Error retrieving tour distances: {str(e)}", 500)


def debug_tours():
    try:
        tours = Tour.objects(secret_tour__ne=True)
        logger.info(f"Debug (standard): Found {tours.count()} non-secret tours")

        raw_tours = Tour.objects(__raw__={'secretTour': {'$ne': True}})
        logger.info(f"Debug (raw): Found {raw_tours.count()} non-secret tours")

        return jsonify({
            "status": "success",
            "results": tours.count(),
            "data": {"data": [tour.to_json() for tour in tours]},
            "raw_results": raw_tours.count(),
            "raw_data": [tour.to_json() for tour in raw_tours]
        }), 200
    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        raise AppError(str(e), 500)

def get_tour(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        logger.debug(f"Converted ObjectId: {object_id} (type: {type(object_id)})")
        logger.debug(f"Querying collection: {Tour._get_collection().name}")

        doc = Tour.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No tour found with that ID', 404)
        doc = doc.populate_guides()
        # Manually fetch and populate reviews
        reviews = Review.objects(tour=doc.id)
        doc.reviews = []
        for review in reviews:
            populated_review = review.populate()
            if populated_review.user and hasattr(populated_review.user, 'name') and hasattr(populated_review.user, 'photo'):
                if isinstance(populated_review.created_at, datetime):
                    doc.reviews.append(populated_review)
                else:
                    logger.warning(f"Skipping review {review.id}: invalid created_at {populated_review.created_at}")
            else:
                logger.warning(f"Skipping review {review.id} for tour {doc.id}: missing user data")
        logger.debug(f"Loaded {len(doc.reviews)} valid reviews for tour {doc.id}")

        # Validate startDates
        if not doc.startDates or not isinstance(doc.startDates[0], datetime):
            logger.warning(f"Tour {doc.id} has invalid startDates: {doc.startDates}")
            doc.startDates = [datetime.utcnow()]

        # Validate start_location
        if not doc.start_location or not hasattr(doc.start_location, 'description'):
            logger.warning(f"Tour {doc.id} has invalid start_location: {doc.start_location}")
            doc.start_location = {'description': 'Unknown Location', 'address': 'N/A'}

        # Include reviews in JSON response
        tour_data = doc.to_json()
        tour_data['reviews'] = [review.to_json() for review in doc.reviews]
        return jsonify({
            "status": "success",
            "data": {
                "data": tour_data
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_tour: {str(e)}\n{traceback.format_exc()}")
        raise AppError(str(e), 500)

def get_tour_by_slug(slug):
    try:
        logger.debug(f"Incoming slug from URL: {slug} (type: {type(slug)})")
        doc = Tour.objects(slug=slug, secret_tour__ne=True).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No tour found with that slug', 404)
        doc = doc.populate_guides()
        # Manually fetch and populate reviews
        reviews = Review.objects(tour=doc.id)
        doc.reviews = []
        for review in reviews:
            populated_review = review.populate()
            if populated_review.user and hasattr(populated_review.user, 'name') and hasattr(populated_review.user, 'photo'):
                if isinstance(populated_review.created_at, datetime):
                    doc.reviews.append(populated_review)
                else:
                    logger.warning(f"Skipping review {review.id}: invalid created_at {populated_review.created_at}")
            else:
                logger.warning(f"Skipping review {review.id} for tour {doc.id}: missing user data")
        logger.debug(f"Loaded {len(doc.reviews)} valid reviews for tour {slug}")

        # Validate startDates
        if not doc.startDates or not isinstance(doc.startDates[0], datetime):
            logger.warning(f"Tour {slug} has invalid startDates: {doc.startDates}")
            doc.startDates = [datetime.utcnow()]

        # Validate start_location
        if not doc.start_location or not hasattr(doc.start_location, 'description'):
            logger.warning(f"Tour {slug} has invalid start_location: {doc.start_location}")
            doc.start_location = {'description': 'Unknown Location', 'address': 'N/A'}

        # Include reviews in JSON response
        tour_data = doc.to_json()
        tour_data['reviews'] = [review.to_json() for review in doc.reviews]
        return jsonify({
            "status": "success",
            "data": {
                "data": tour_data
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_tour_by_slug: {str(e)}\n{traceback.format_exc()}")
        raise AppError(str(e), 500)

# Route handlers (updated to use local functions with decorators)
get_all_tours = get_all_tours
get_tour = get_one_tour
get_tour_by_slug = get_tour_by_slug
create_tour = upload_tour_images()(resize_tour_images()(create_one_tour))
update_tour = upload_tour_images()(resize_tour_images()(update_one_tour))
delete_tour = delete_one_tour