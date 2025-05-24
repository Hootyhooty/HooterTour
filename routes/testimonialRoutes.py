from flask import Blueprint, request, g
from controllers.testimonialController import get_all_testimonials, create_testimonial, get_testimonial, update_testimonial, delete_testimonial
from controllers.authController import protect, restrict_to
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Blueprint for testimonial routes
testimonial_routes = Blueprint('testimonial_routes', __name__, url_prefix='/api/v1/testimonials')

# Testimonial routes
testimonial_routes.route('/', methods=['GET'], endpoint='get_all_testimonials')(protect(restrict_to('admin')(get_all_testimonials)))
testimonial_routes.route('/', methods=['POST'], endpoint='create_testimonial')(protect(restrict_to('user')(create_testimonial)))
testimonial_routes.route('/<id>', methods=['GET'], endpoint='get_testimonial')(protect(restrict_to('admin')(get_testimonial)))
testimonial_routes.route('/<id>', methods=['PATCH'], endpoint='update_testimonial')(protect(restrict_to('user')(update_testimonial)))
testimonial_routes.route('/<id>', methods=['DELETE'], endpoint='delete_testimonial')(protect(restrict_to('user', 'admin')(delete_testimonial)))

# Before request to log route access
@testimonial_routes.before_request
def log_request():
    user_email = g.user.email if hasattr(g, 'user') else 'Anonymous'
    logger.info(f"Accessing testimonial route: {request.method} {request.path} | User: {user_email}")