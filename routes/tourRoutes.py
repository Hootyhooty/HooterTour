from flask import Blueprint, request, g
from controllers.tourController import (
    get_all_tours, get_tour, create_tour, update_tour, delete_tour,
    get_tour_stats, get_monthly_plan, get_tours_within, get_distances,
    alias_top_tours, debug_tours, get_tour_by_slug  # Add new function
)
from controllers.authController import protect, restrict_to
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Blueprint for tour routes
tour_routes = Blueprint('tour_routes', __name__, url_prefix='/api/v1/tours')

# Public Routes (No Authentication Required)
tour_routes.route('/top-5-cheap', methods=['GET'], endpoint='top_5_cheap')(alias_top_tours()(get_all_tours))
tour_routes.route('/tour-stats', methods=['GET'], endpoint='tour_stats')(get_tour_stats)
tour_routes.route('/', methods=['GET'], endpoint='get_all_tours')(get_all_tours)
tour_routes.route('/<id>', methods=['GET'], endpoint='get_tour')(get_tour)
tour_routes.route('/slug/<slug>', methods=['GET'], endpoint='get_tour_by_slug')(get_tour_by_slug)  # New route for slug-based lookup
tour_routes.route('/tours-within', methods=['GET'], endpoint='tours_within')(get_tours_within)
tour_routes.route('/distances', methods=['GET'], endpoint='distances')(get_distances)

# Admin/Lead-Guide Routes (Requires Authentication and Specific Roles)
tour_routes.route('/monthly-plan', methods=['GET'], endpoint='monthly_plan')(protect(restrict_to('admin', 'lead-guide', 'guide')(get_monthly_plan)))
tour_routes.route('/', methods=['POST'], endpoint='create_tour')(protect(restrict_to('admin', 'lead-guide')(create_tour)))
tour_routes.route('/<id>', methods=['PATCH'], endpoint='update_tour')(protect(restrict_to('admin', 'lead-guide')(update_tour)))
tour_routes.route('/<id>', methods=['DELETE'], endpoint='delete_tour')(protect(restrict_to('admin', 'lead-guide')(delete_tour)))
tour_routes.route('/debug', methods=['GET'], endpoint='debug_tours')(debug_tours)

# Before request to log route access
@tour_routes.before_request
def log_request():
    user_email = g.user.email if hasattr(g, 'user') else 'Anonymous'
    query_params = request.args.to_dict()
    logger.info(
        f"Accessing tour route: {request.method} {request.path} | "
        f"User: {user_email} | Query Params: {query_params}"
    )