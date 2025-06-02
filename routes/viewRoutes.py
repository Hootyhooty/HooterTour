import os
from flask import Blueprint
from hashids import Hashids
from Utils.AppError import AppError
from controllers.viewController import (
    home, get_tour, get_account, get_my_tours,
    destination, about, contact, service, error, package, booking, team, testimonial, alerts, dashboard, serve_image,
    guide_profile, payment, booking_summary
)
from controllers.authController import is_logged_in, protect, logger
from bson import ObjectId

HASHIDS_SALT = os.getenv('HASHIDS_SALT', 'default-salt')
HASHIDS_MIN_LENGTH = int(os.getenv('HASHIDS_MIN_LENGTH', 16))
HASHIDS_ALPHABET = os.getenv('HASHIDS_ALPHABET', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH, alphabet=HASHIDS_ALPHABET)


# Define the view_routes blueprint
view_routes = Blueprint('view_routes', __name__)

# Routes for rendering pages (apply is_logged_in to check login status)
view_routes.route('/', methods=['GET', 'POST'])(is_logged_in(alerts(home)))
view_routes.route('/destination', methods=['GET', 'POST'])(is_logged_in(alerts(destination)))
view_routes.route('/destination/<slug>', methods=['GET'], endpoint='get_tour_by_slug')(is_logged_in(alerts(get_tour)))
view_routes.route('/about', methods=['GET', 'POST'])(is_logged_in(alerts(about)))
view_routes.route('/contact', methods=['GET', 'POST'])(is_logged_in(alerts(contact)))
view_routes.route('/service', methods=['GET', 'POST'])(is_logged_in(alerts(service)))
view_routes.route('/404', methods=['GET', 'POST'])(is_logged_in(alerts(error)))
view_routes.route('/package', methods=['GET', 'POST'])(is_logged_in(alerts(package)))
view_routes.route('/booking', methods=['GET', 'POST'])(is_logged_in(alerts(booking)))
view_routes.route('/team', methods=['GET', 'POST'])(is_logged_in(alerts(team)))
view_routes.route('/testimonial', methods=['GET', 'POST'])(is_logged_in(alerts(testimonial)))
view_routes.route('/dashboard/<profile_slug>', methods=['GET', 'POST'])(is_logged_in(protect(dashboard)))
view_routes.route('/image/<filename>')(serve_image)
view_routes.route('/about/<name>', methods=['GET'], endpoint='guide_profile')(is_logged_in(alerts(guide_profile)))
#view_routes.route('/payment/<tour_id>', methods=['GET'], endpoint='payment')(is_logged_in(protect(payment)))
#view_routes.route('/booking-summary/<booking_id>', methods=['GET'], endpoint='booking_summary')(is_logged_in(protect(booking_summary)))

# Additional routes from viewController
view_routes.route('/overview', endpoint='overview')(is_logged_in(alerts(home)))
view_routes.route('/tour/<slug>')(is_logged_in(alerts(get_tour)))
view_routes.route('/account')(is_logged_in(alerts(get_account)))
view_routes.route('/me')(is_logged_in(protect(get_my_tours)))

@view_routes.route('/payment/<hashed_id>', methods=['GET'], endpoint='payment')
@is_logged_in
@protect
def payment_wrapper(hashed_id):
    try:
        decoded = hashids.decode(hashed_id)
        if not decoded:
            logger.error(f"Failed to decode hashed_id: {hashed_id}")
            raise AppError("Invalid tour ID", 400)
        tour_id_int = decoded[0]
        # Convert integer to 24-char hex ObjectId
        tour_id_str = f"{tour_id_int:024x}"[:24]
        try:
            tour_id = ObjectId(tour_id_str)
            # Verify tour exists
            tour = Tour.objects(id=tour_id).first()
            if not tour:
                logger.error(f"No tour found for ID: {tour_id_str}")
                raise AppError("Tour not found", 404)
        except Exception as e:
            logger.error(f"Invalid ObjectId format: {tour_id_str}, error: {str(e)}")
            raise AppError("Invalid tour ID format", 400)
        return payment(tour_id_str)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error decoding hashed tour ID {hashed_id}: {str(e)}")
        raise AppError("Invalid tour ID", 400)

@view_routes.route('/booking-summary/<hashed_id>', methods=['GET'], endpoint='booking_summary')
@is_logged_in
@protect
def booking_summary_wrapper(hashed_id):
    try:
        decoded = hashids.decode(hashed_id)
        if not decoded:
            raise AppError("Invalid booking ID", 400)
        booking_id = f"{decoded[0]:024x}"  # Convert to 24-char hex ObjectId
        return booking_summary(booking_id)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error decoding hashed booking ID {hashed_id}: {str(e)}")
        raise AppError("Invalid booking ID", 400)