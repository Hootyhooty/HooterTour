import os
from dotenv import load_dotenv
from flask import request, jsonify, g
import stripe
from models.tourModel import Tour
from models.userModel import User
from models.bookingModel import Booking
from Utils.AppError import AppError
from Utils.apiFeature import APIFeatures
from bson import ObjectId
import logging
from datetime import datetime
from dateutil import parser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')


# Utility functions (moved from handlerFactory)
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


# Helper function to create booking after checkout
def create_booking_checkout(session):
    try:
        tour_id = session.client_reference_id
        user = User.objects(email=session.customer_email).first()
        if not user:
            logger.error(f"No user found with email: {session.customer_email}")
            raise AppError(f"No user found with email: {session.customer_email}", 404)
        tour = Tour.objects(id=tour_id).first()
        if not tour:
            logger.error(f"No tour found with ID: {tour_id}")
            raise AppError(f"No tour found with ID: {tour_id}", 404)
        price = session.amount_total / 100  # Convert from cents to dollars
        booking = Booking(tour=tour_id, user=user.id, price=price, tour_slug=tour.slug)
        booking.save()
        logger.info(f"Booking created for tour {tour_id} by user {user.email}")
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to create booking: {str(e)}")
        raise AppError(f"Failed to create booking: {str(e)}", 500)


# Booking-specific handlers (moved from handlerFactory)
def get_all_bookings():
    try:
        filter_kwargs = {}
        if 'tourId' in request.args:
            filter_kwargs['tour'] = request.args.get('tourId')

        query = Booking.objects(__raw__={**filter_kwargs})
        logger.debug(f"Collection name for Booking: {Booking._get_collection().name}")
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

        logger.debug(f"Final bookings count: {len(docs)}")
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
        logger.error(f"Error in get_all_bookings: {str(e)}")
        raise AppError(str(e), 500)


def get_one_booking(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        logger.debug(f"Converted ObjectId: {object_id} (type: {type(object_id)})")
        logger.debug(f"Querying collection: {Booking._get_collection().name}")

        doc = Booking.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No booking found with that ID', 404)
        logger.debug(f"Found booking: {doc.to_json()}")

        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_one_booking: {str(e)}")
        raise AppError(str(e), 500)


def create_one_booking():
    try:
        data = request.get_json()
        logger.debug(f"Incoming create data: {data}")
        data = transform_data(data)
        logger.debug(f"Transformed create data: {data}")
        doc = Booking(**data)
        doc.save()
        return jsonify({
            "status": "success",
            "data": {
                "data": doc.to_json()
            }
        }), 201
    except Exception as e:
        logger.error(f"Error in create_one_booking: {str(e)}")
        raise AppError(str(e), 500)


def update_one_booking(id):
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

        doc = Booking.objects(id=object_id).first()
        if not doc:
            raise AppError('No booking found with that ID', 404)
        doc.update(**data)
        updated_doc = Booking.objects(id=object_id).first()
        return jsonify({
            "status": "success",
            "data": {
                "data": updated_doc.to_json()
            }
        }), 200
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in update_one_booking: {str(e)}")
        raise AppError(str(e), 500)


def delete_one_booking(id):
    try:
        logger.debug(f"Incoming ID from URL: {id} (type: {type(id)})")
        try:
            object_id = ObjectId(id)
        except Exception as e:
            logger.error(f"Invalid ID format: {id}, error: {str(e)}")
            raise AppError("Invalid ID format", 400)

        doc = Booking.objects(id=object_id).first()
        if not doc:
            logger.debug("Document not found")
            raise AppError('No booking found with that ID', 404)

        doc.delete()
        logger.debug(f"Deleted booking with ID: {id}")
        return jsonify({
            "status": "success",
            "data": None
        }), 204
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_one_booking: {str(e)}")
        raise AppError(str(e), 500)

# Route handlers
def get_checkout_session(tourId):
    try:
        if not tourId:
            raise AppError('Tour ID is required', 400)

        tour = Tour.objects(id=tourId).first()
        if not tour:
            raise AppError('No tour found with that ID', 404)

        if not tour.stripe_payment_link:
            raise AppError('No payment link configured for this tour', 400)

        if not hasattr(g, 'user'):
            raise AppError('User not authenticated', 401)

        user = g.user

        # Create a booking before redirecting to Stripe
        price = tour.price  # Price in dollars
        booking = Booking(
            tour=tour.id,
            user=user.id,
            price=price,
            tour_slug=tour.slug,
            paid=False  # Set to False initially; update via webhook
        )
        booking.save()
        logger.info(f"Booking created for tour {tourId} by user {user.email}: Booking ID {str(booking.id)}")

        # Attach the booking ID to the payment link as a query parameter
        # This will be used in the success redirect to show the booking summary
        stripe_payment_link = f"{tour.stripe_payment_link}&client_reference_id={str(booking.id)}"

        logger.info(f"Redirecting to Stripe payment link for tour {tourId}: {stripe_payment_link}")
        return jsonify({
            "status": "success",
            "redirect_url": stripe_payment_link
        }), 200

    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_checkout_session: {str(e)}")
        raise AppError(str(e), 500)

def webhook_checkout():
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        logger.debug(f"Webhook payload: {payload}")
        logger.debug(f"Webhook signature: {sig_header}")

        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )

        if event['type'] == 'checkout.session.completed':
            logger.debug(f"Processing checkout.session.completed: {event['data']['object']}")
            session = event['data']['object']
            booking_id = session.get('client_reference_id')
            if not booking_id:
                logger.error("No booking ID found in client_reference_id")
                return jsonify({'error': 'No booking ID provided'}), 400

            booking = Booking.objects(id=booking_id).first()
            if not booking:
                logger.error(f"No booking found with ID: {booking_id}")
                return jsonify({'error': 'Booking not found'}), 404

            # Update the booking to mark it as paid
            booking.update(paid=True)
            logger.info(f"Booking {booking_id} marked as paid after Stripe checkout session completion")

        return jsonify({'received': True}), 200

    except ValueError as e:
        logger.error(f"Webhook error: Invalid payload - {str(e)}")
        return jsonify({'error': f"Webhook error: {str(e)}"}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook error: Invalid signature - {str(e)}")
        return jsonify({'error': f"Webhook error: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise AppError(str(e), 500)

# Route handlers using local functions
get_all_bookings = get_all_bookings
get_booking = get_one_booking
create_booking = create_one_booking
update_booking = update_one_booking
delete_booking = delete_one_booking