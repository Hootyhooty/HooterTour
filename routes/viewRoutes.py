from flask import Blueprint, request
from bson import ObjectId
from Utils.AppError import AppError
from controllers.viewController import (
    home, get_tour, get_my_tours,
    destination, about, contact, service, error, team, testimonial, alerts, dashboard, serve_image,
    guide_profile, payment, booking_summary, mock_payment, mock_payment_success, mock_webhook
)
from controllers.authController import is_logged_in, protect, logger

# Define the view_routes blueprint
view_routes = Blueprint('view_routes', __name__)

# Existing routes (unchanged)
view_routes.route('/', methods=['GET', 'POST'])(is_logged_in(alerts(home)))
view_routes.route('/destination', methods=['GET', 'POST'])(is_logged_in(alerts(destination)))
view_routes.route('/destination/<slug>', methods=['GET'], endpoint='get_tour_by_slug')(is_logged_in(alerts(get_tour)))
view_routes.route('/about', methods=['GET', 'POST'])(is_logged_in(alerts(about)))
view_routes.route('/contact', methods=['GET', 'POST'])(is_logged_in(alerts(contact)))
view_routes.route('/service', methods=['GET', 'POST'])(is_logged_in(alerts(service)))
view_routes.route('/404', methods=['GET', 'POST'])(is_logged_in(alerts(error)))
view_routes.route('/team', methods=['GET', 'POST'])(is_logged_in(alerts(team)))
view_routes.route('/testimonial', methods=['GET', 'POST'])(is_logged_in(alerts(testimonial)))
view_routes.route('/dashboard/<profile_slug>', methods=['GET', 'POST'])(is_logged_in(protect(dashboard)))
view_routes.route('/image/<filename>')(serve_image)
view_routes.route('/about/<name>', methods=['GET'], endpoint='guide_profile')(is_logged_in(alerts(guide_profile)))
view_routes.route('/overview', endpoint='overview')(is_logged_in(alerts(home)))
view_routes.route('/tour/<slug>')(is_logged_in(alerts(get_tour)))
view_routes.route('/me')(is_logged_in(protect(get_my_tours)))
view_routes.route('/mock-payment', methods=['GET'], endpoint='mock_payment')(is_logged_in(protect(mock_payment)))
view_routes.route('/mock-webhook', methods=['POST'], endpoint='mock_webhook')(mock_webhook)
view_routes.route('/mock-payment-success', methods=['POST'], endpoint='mock_payment_success')(is_logged_in(protect(mock_payment_success)))

# Updated payment route
@view_routes.route('/payment/<id>', methods=['GET'], endpoint='payment')
@is_logged_in
@protect
def payment_wrapper(id):
    try:
        # Validate ObjectID
        try:
            ObjectId(id)  # Ensure id is a valid ObjectID
        except Exception:
            logger.error(f"Invalid tour ID format: {id}")
            raise AppError("Invalid tour ID format", 400)
        return payment(id)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing tour ID {id}: {str(e)}")
        raise AppError("Invalid tour ID", 400)

# Updated booking summary route
@view_routes.route('/booking-summary/<id>', methods=['GET'], endpoint='booking_summary')
@is_logged_in
@protect
def booking_summary_wrapper(id):
    try:
        # Validate ObjectID
        try:
            ObjectId(id)  # Ensure id is a valid ObjectID
        except Exception:
            logger.error(f"Invalid booking ID format: {id}")
            raise AppError("Invalid booking ID format", 400)
        return booking_summary(id)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing booking ID {id}: {str(e)}")
        raise AppError("Invalid booking ID", 400)