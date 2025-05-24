from flask import Blueprint, request, g
from controllers.reviewController import get_all_reviews, create_review, get_review, update_review, delete_review
from controllers.authController import protect, restrict_to
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Blueprint for review routes
review_routes = Blueprint('review_routes', __name__, url_prefix='/api/v1/reviews')

# Review routes
review_routes.route('/', methods=['GET'], endpoint='get_all_reviews')(protect(get_all_reviews))
review_routes.route('/', methods=['POST'], endpoint='create_review')(protect(restrict_to('user')(create_review)))
review_routes.route('/<id>', methods=['GET'], endpoint='get_review')(protect(get_review))
review_routes.route('/<id>', methods=['PATCH'], endpoint='update_review')(protect(restrict_to('user', 'admin')(update_review)))
review_routes.route('/<id>', methods=['DELETE'], endpoint='delete_review')(protect(restrict_to('user', 'admin')(delete_review)))

# Before request to log route access
@review_routes.before_request
def log_request():
    user_email = g.user.email if hasattr(g, 'user') else 'Anonymous'
    logger.info(f"Accessing review route: {request.method} {request.path} | User: {user_email}")