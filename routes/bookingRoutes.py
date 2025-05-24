from flask import Blueprint, request, g
from controllers.bookingController import get_checkout_session, get_all_bookings, create_booking, get_booking, update_booking, delete_booking, webhook_checkout
from controllers.authController import protect, restrict_to
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Blueprint for booking routes
booking_routes = Blueprint('booking_routes', __name__, url_prefix='/api/v1/bookings')

# Booking routes
booking_routes.route('/checkout-session/<tourId>', methods=['GET'], endpoint='get_checkout_session')(protect(get_checkout_session))
# Description: Create a Stripe checkout session for a tour
# Request: GET /api/v1/bookings/checkout-session/<tourId>
# Response: 200, { "status": "success", "session": {...} }

booking_routes.route('/webhook-checkout', methods=['POST'], endpoint='webhook_checkout')(webhook_checkout)
# Description: Handle Stripe webhook for checkout session completion
# Request: POST /api/v1/bookings/webhook-checkout
# Body: Stripe webhook payload
# Response: 200, { "received": true }

booking_routes.route('/', methods=['GET'], endpoint='get_all_bookings')(protect(restrict_to('admin', 'lead-guide')(get_all_bookings)))
# Description: Get all bookings (admin or lead-guide only)
# Request: GET /api/v1/bookings?tourId=<tour_id>
# Response: 200, { "status": "success", "results": number, "data": { "data": [...] } }

booking_routes.route('/', methods=['POST'], endpoint='create_booking')(protect(restrict_to('admin', 'lead-guide')(create_booking)))
# Description: Create a new booking (admin or lead-guide only)
# Request: POST /api/v1/bookings
# Body: { "tour": "tour_id", "user": "user_id", "price": number }
# Response: 201, { "status": "success", "data": { "data": {...} } }

booking_routes.route('/<id>', methods=['GET'], endpoint='get_booking')(protect(restrict_to('admin', 'lead-guide')(get_booking)))
# Description: Get a booking by ID (admin or lead-guide only)
# Request: GET /api/v1/bookings/<id>
# Response: 200, { "status": "success", "data": { "data": {...} } }

booking_routes.route('/<id>', methods=['PATCH'], endpoint='update_booking')(protect(restrict_to('admin', 'lead-guide')(update_booking)))
# Description: Update a booking by ID (admin or lead-guide only)
# Request: PATCH /api/v1/bookings/<id>
# Body: { "price": number }
# Response: 200, { "status": "success", "data": { "data": {...} } }

booking_routes.route('/<id>', methods=['DELETE'], endpoint='delete_booking')(protect(restrict_to('admin', 'lead-guide')(delete_booking)))
# Description: Delete a booking by ID (admin or lead-guide only)
# Request: DELETE /api/v1/bookings/<id>
# Response: 204, { "status": "success", "data": null }

# Before request to log route access
@booking_routes.before_request
def log_request():
    if request.path.endswith('/webhook-checkout'):
        return  # Skip logging for webhook
    user_email = g.user.email if hasattr(g, 'user') else 'Anonymous'
    logger.info(f"Accessing booking route: {request.method} {request.path} | User: {user_email}")