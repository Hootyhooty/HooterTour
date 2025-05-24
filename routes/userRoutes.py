from flask import Blueprint, request, g
from controllers.userController import (
    get_all_users, get_user, create_user, update_user, delete_user,
    set_current_user_id, update_me, delete_me, upload_user_photo, resize_user_photo, check_email,
    get_current_user_data, serve_user_image, upload_image_to_imgs
)
from controllers.authController import (
    protect, restrict_to, signup, login, logout, forgot_password, reset_password, update_password
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Blueprint for user routes
user_routes = Blueprint('user_routes', __name__, url_prefix='/api/v1/users')

# Public Routes (No Authentication Required)
user_routes.route('/signup', methods=['POST'], endpoint='signup')(signup)
user_routes.route('/login', methods=['POST'], endpoint='login')(login)
user_routes.route('/logout', methods=['GET'], endpoint='logout')(logout)
user_routes.route('/forgot-password', methods=['POST'], endpoint='forgot_password')(forgot_password)
user_routes.route('/reset-password/<token>', methods=['PATCH'], endpoint='reset_password')(reset_password)

# Check if email exists
user_routes.route('/check-email', methods=['POST'], endpoint='check_email')(check_email)

# Serve user image
user_routes.route('/image/<profile_slug>', methods=['GET'], endpoint='serve_user_image')(serve_user_image)

# Authenticated User Routes (Requires Authentication)
user_routes.route('/update-my-password', methods=['PATCH'], endpoint='update_password')(protect(update_password))
user_routes.route('/me', methods=['GET'], endpoint='get_me')(protect(get_current_user_data))
user_routes.route('/update-me', methods=['PATCH'], endpoint='update_me')(protect(upload_user_photo()(resize_user_photo()(set_current_user_id(update_me)))))
user_routes.route('/delete-me', methods=['DELETE'], endpoint='delete_me')(protect(set_current_user_id(delete_me)))

# Admin Routes (Requires Authentication and Admin Role)
user_routes.route('/', methods=['GET'], endpoint='get_all_users')(protect(restrict_to('admin')(get_all_users)))
user_routes.route('/', methods=['POST'], endpoint='create_user')(protect(restrict_to('admin')(create_user)))
user_routes.route('/<id>', methods=['GET'], endpoint='get_user')(protect(restrict_to('admin')(get_user)))
user_routes.route('/<id>', methods=['PATCH'], endpoint='update_user')(protect(restrict_to('admin')(update_user)))
user_routes.route('/<id>', methods=['DELETE'], endpoint='delete_user')(protect(restrict_to('admin')(delete_user)))
user_routes.route('/upload-image-to-imgs', methods=['POST'], endpoint='upload_image_to_imgs')(protect(restrict_to('admin')(upload_user_photo()(upload_image_to_imgs))))

# Before request to log route access
@user_routes.before_request
def log_request():
    user_email = g.user.email if hasattr(g, 'user') else 'Anonymous'
    path = request.path
    if '/image/' in path:
        parts = path.split('/')
        masked_id = parts[-1][:8] + '...' if parts[-1] else 'unknown'
        path = '/'.join(parts[:-1] + [masked_id])
    logger.info(f"Accessing user route: {request.method} {path} | User: {user_email}")