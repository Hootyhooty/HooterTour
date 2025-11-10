import os
from dotenv import load_dotenv
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
import hashlib
import datetime
from flask import request, jsonify, make_response, g, current_app, url_for
from functools import wraps
from mongoengine import ValidationError
from models.userModel import User, Role
from Utils.AppError import AppError
from Utils.email import Email

import logging
#is_prod = current_app.config.get('ENV') == 'production'
is_prod = os.getenv('ENV') == 'production'


# Debug JWT module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Validate environment variables
JWT_SECRET = os.getenv('JWT_SECRET')
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is not set")

JWT_COOKIE_EXPIRES_IN = os.getenv('JWT_COOKIE_EXPIRES_IN', '90')
try:
    JWT_COOKIE_EXPIRES_IN = int(JWT_COOKIE_EXPIRES_IN)
except ValueError:
    raise ValueError("JWT_COOKIE_EXPIRES_IN must be an integer (days)")

# Helper functions
def sign_token(user_id: str) -> str:
    """
    Generate a JWT token for the given user ID.
    """
    logger.debug(f"Generating JWT token for user ID: {user_id}")
    try:
        payload = {
            'id': str(user_id),
            'iat': int(datetime.datetime.utcnow().timestamp()),
            'exp': int((datetime.datetime.utcnow() + datetime.timedelta(days=JWT_COOKIE_EXPIRES_IN)).timestamp())
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    except AttributeError as e:
        logger.error(f"JWT encode failed: {str(e)}")
        raise AppError("Token generation failed: Invalid JWT library", 500)

def create_send_token(user: User, status_code: int) -> 'make_response':
    """
    Create a JWT token, set it in a cookie, and return a response with a redirect URL.
    """
    token = sign_token(user.id)
    expires_in = JWT_COOKIE_EXPIRES_IN * 24 * 60 * 60 * 1000  # Convert days to milliseconds
    expires = datetime.datetime.utcnow() + datetime.timedelta(milliseconds=expires_in)

    # Generate the dashboard URL using profile_slug
    dashboard_url = url_for('view_routes.dashboard', profile_slug=user.profile_slug, _external=True)

    # Create response
    response = make_response(jsonify({
        'status': 'success',
        'token': token,
        'redirect_url': dashboard_url,  # Include the redirect URL
        'data': {'user': user.to_json()}
    }))
    response.status_code = status_code

    # Set JWT cookie with security settings
    response.set_cookie(
        'jwt',
        token,
        expires=expires,
        httponly=True,
        secure=is_prod,
        samesite='None' if is_prod else 'Lax'
    )

    # Remove sensitive fields from user
    user.password = None
    logger.info(f"Token created and sent for user: {user.email}")
    return response

# Route handlers
def signup():
    """
    Handle user signup: create a new user, send a welcome email, and return a JWT token.
    """
    try:
        data = request.get_json() or {}
        logger.debug(f"Signup payload: {data}")

        # Validate required fields
        required_fields = ['name', 'email', 'password', 'passwordConfirm']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            logger.warning(f"Signup attempt missing fields: {missing_fields}")
            raise AppError(f"Missing required fields: {', '.join(missing_fields)}", 400)

        # Validate password length and confirmation
        password = data.get('password')
        password_confirm = data.get('passwordConfirm')
        if len(password) < 8:
            logger.warning("Signup attempt with password too short")
            raise AppError("Password must be at least 8 characters long", 400)
        if password != password_confirm:
            logger.warning("Signup attempt with mismatched passwords")
            raise AppError("Passwords do not match", 400)

        # Validate name length
        if len(data.get('name', '')) < 2:
            logger.warning("Signup attempt with name too short")
            raise AppError("Name must be at least 2 characters long", 400)

        # Validate role
        role = data.get('role', Role.USER.value)
        if role not in [r.value for r in Role]:
            logger.warning(f"Signup attempt with invalid role: {role}")
            raise AppError(f"Invalid role: {role}", 400)
        if role == Role.ADMIN.value:
            logger.warning("Signup attempt with admin role")
            raise AppError("Cannot assign admin role during signup", 403)

        # Check if email already exists
        if User.objects(email=data.get('email')).first():
            logger.warning(f"Signup attempt with existing email: {data.get('email')}")
            raise AppError("Email already exists", 400)

        # Remove fields that should be system-generated
        data.pop('profile_slug', None)  # Let model generate HashID-based profile_slug
        data.pop('passwordConfirm', None)  # Not stored in model

        # Create new user
        new_user = User(
            name=data.get('name'),
            email=data.get('email'),
            password=password,
            role=role
        )
        logger.debug(f"New user before save: name={new_user.name}, email={new_user.email}, role={new_user.role}")
        new_user.save()

        # Send welcome email (non-critical)
        try:
            url = f"{request.url_root}me"
            email = Email(new_user, url)
            email.send_welcome()
            logger.info(f"Welcome email sent to: {new_user.email}")
        except Exception as email_error:
            logger.error(f"Failed to send welcome email to {new_user.email}: {str(email_error)}")
            # Continue despite email failure

        logger.info(f"User signed up successfully: {new_user.email}")
        return create_send_token(new_user, 201)
    except ValidationError as e:
        logger.error(f"Validation error during signup: {str(e)}")
        raise AppError(f"Validation error: {str(e)}", 400)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during signup: {str(e)}")
        raise AppError(f"Error creating user: {str(e)}", 500)

def login():
    """
    Handle user login: verify credentials and return a JWT token.
    """
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')

        # Check if email and password are provided
        if not email or not password:
            logger.warning("Login attempt without email or password")
            raise AppError('Please provide email and password!', 400)

        # Check if user exists and password is correct
        user = User.objects(email=email, active=True).first()
        if not user or not user.correct_password(password, user.password):
            logger.warning(f"Failed login attempt for email: {email}")
            raise AppError('Incorrect email or password', 401)

        logger.info(f"User logged in successfully: {user.email}")
        return create_send_token(user, 200)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise AppError(f"Error logging in: {str(e)}", 500)

def logout():
    """
    Handle user logout: clear the JWT cookie.
    """
    response = make_response(jsonify({'status': 'success'}))
    response.set_cookie(
        'jwt',
        '',
        expires=datetime.datetime.utcnow(),
        httponly=True,
        samesite='Strict'
    )
    logger.info("User logged out successfully")
    return response, 200

def protect(f):
    """
    Decorator to protect routes: verify JWT token and set g.user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get token from Authorization header or cookie
            token = None
            if 'authorization' in request.headers and request.headers['authorization'].startswith('Bearer'):
                token = request.headers['authorization'].split(' ')[1]
                logger.info("Token found in Authorization header")
            elif 'jwt' in request.cookies:
                token = request.cookies.get('jwt')
                logger.info("Token found in cookie")

            if not token:
                logger.warning("Access attempt without token")
                raise AppError('You are not logged in! Please log in to get access.', 401)

            # Verify token
            logger.debug(f"Decoding token: {token}")
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            logger.debug(f"Token decoded: {decoded}")

            # Check if user exists
            current_user = User.objects(id=decoded['id'], active=True).first()
            if not current_user:
                logger.warning(f"Token refers to non-existent user: {decoded['id']}")
                raise AppError('The user belonging to this token does no longer exist.', 401)

            # Check if password was changed after token issuance
            if current_user.changed_password_after(decoded['iat']):
                logger.warning(f"Password changed for user: {current_user.email}")
                raise AppError('User recently changed password! Please log in again.', 401)

            # Set user in g for access in the route
            g.user = current_user
            logger.info(f"User authenticated: {current_user.email}")

            # Call the original function
            return f(*args, **kwargs)
        except ExpiredSignatureError:
            logger.warning("Access attempt with expired token")
            raise AppError('Your token has expired! Please log in again.', 401)
        except JWTError as e:
            logger.warning(f"Access attempt with invalid token: {str(e)}")
            raise AppError('Invalid token! Please log in again.', 401)
        except AppError as e:
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in protect decorator: {str(e)}")
            raise AppError(f"Authentication error: {str(e)}", 500)
    return decorated_function

def is_logged_in(f):
    """
    Decorator to check if a user is logged in for view routes.
    Redirects to login if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'jwt' in request.cookies:
            try:
                # Verify token
                decoded = jwt.decode(request.cookies.get('jwt'), JWT_SECRET, algorithms=['HS256'])

                # Check if user exists
                current_user = User.objects(id=decoded['id'], active=True).first()
                if not current_user:
                    logger.warning(f"Token refers to non-existent user in is_logged_in: {decoded['id']}")
                    return f(*args, **kwargs)  # Proceed without setting g.user

                # Check if password was changed
                if current_user.changed_password_after(decoded['iat']):
                    logger.warning(f"Password changed for user in is_logged_in: {current_user.email}")
                    return f(*args, **kwargs)  # Proceed without setting g.user

                # Set user in g
                g.user = current_user
                logger.debug(f"User authenticated in is_logged_in: {current_user.email}")
            except jwt.ExpiredSignatureError:
                logger.warning("Expired token in is_logged_in")
            except jwt.InvalidTokenError:
                logger.warning("Invalid token in is_logged_in")
        return f(*args, **kwargs)  # Always proceed to the view function
    return decorated_function

def restrict_to(*roles):
    """
    Middleware to restrict access to specific roles.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not hasattr(g, 'user'):
                logger.warning("Access attempt without authenticated user")
                raise AppError('You must be logged in to perform this action', 401)
            if g.user.role.value not in roles:  # Use .value since role is an Enum
                logger.warning(f"Access denied for user {g.user.email} with role {g.user.role.value}")
                raise AppError('You do not have permission to perform this action', 403)
            return f(*args, **kwargs)
        return wrapped
    return decorator

def forgot_password():
    """
    Handle password reset request: generate a reset token and send it via email.
    """
    try:
        data = request.get_json() or {}
        email = data.get('email')

        # Find user
        user = User.objects(email=email, active=True).first()
        if not user:
            logger.warning(f"Password reset requested for non-existent email: {email}")
            raise AppError('There is no user with that email address.', 404)

        # Generate reset token
        reset_token = user.create_password_reset_token()
        user.save()

        # Send reset email
        try:
            reset_url = f"{request.url_root}api/v1/users/resetPassword/{reset_token}"
            email_instance = Email(user, reset_url)
            email_instance.send_password_reset()
            logger.info(f"Password reset token sent to: {user.email}")
        except Exception as email_error:
            logger.error(f"Failed to send password reset email to {user.email}: {str(email_error)}")
            # Clean up token but continue
            user.password_reset_token = None
            user.password_reset_expires = None
            user.save()

        return jsonify({
            'status': 'success',
            'message': 'Token sent to email!'
        }), 200
    except AppError as e:
        # Clean up reset token on failure
        user = User.objects(email=email, active=True).first()
        if user:
            user.password_reset_token = None
            user.password_reset_expires = None
            user.save()
        raise e
    except Exception as e:
        # Clean up reset token on failure
        user = User.objects(email=email, active=True).first()
        if user:
            user.password_reset_token = None
            user.password_reset_expires = None
            user.save()
        logger.error(f"Error sending password reset email: {str(e)}")
        raise AppError('There was an error sending the email. Try again later!', 500)

def reset_password():
    """
    Handle password reset: validate token and update password.
    """
    try:
        # Find user by reset token
        hashed_token = hashlib.sha256(request.view_args['token'].encode()).hexdigest()
        user = User.objects(
            password_reset_token=hashed_token,
            password_reset_expires__gt=datetime.datetime.utcnow(),
            active=True
        ).first()

        if not user:
            logger.warning("Invalid or expired password reset token")
            raise AppError('Token is invalid or has expired', 400)

        # Update password
        data = request.get_json() or {}
        # Validate required fields
        if not data.get('password') or not data.get('passwordConfirm'):
            logger.warning("Password reset attempt missing password or passwordConfirm")
            raise AppError("Password and passwordConfirm are required", 400)

        password = data.get('password')
        password_confirm = data.get('passwordConfirm')
        if len(password) < 8:
            logger.warning("Password reset attempt with password too short")
            raise AppError("Password must be at least 8 characters long", 400)
        if password != password_confirm:
            logger.warning("Password reset attempt with mismatched passwords")
            raise AppError("Passwords do not match", 400)

        user.password = password
        user.password_confirm = password_confirm
        user.password_reset_token = None
        user.password_reset_expires = None
        user.save()

        logger.info(f"Password reset successfully for user: {user.email}")
        return create_send_token(user, 200, request)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise AppError(f"Error resetting password: {str(e)}", 400)

def update_password():
    """
    Handle password update for logged-in user.
    """
    try:
        # Ensure user is authenticated
        if not hasattr(g, 'user'):
            logger.warning("Password update attempt without authenticated user")
            raise AppError('You must be logged in to update your password', 401)

        user = User.objects(id=g.user.id, active=True).first()

        # Verify current password
        data = request.get_json() or {}
        if not data.get('passwordCurrent') or not data.get('password') or not data.get('passwordConfirm'):
            logger.warning("Password update attempt missing required fields")
            raise AppError("Current password, new password, and passwordConfirm are required", 400)

        if not user.correct_password(data.get('passwordCurrent'), user.password):
            logger.warning(f"Password update failed for user {user.email}: incorrect current password")
            raise AppError('Your current password is wrong.', 401)

        # Update password
        password = data.get('password')
        password_confirm = data.get('passwordConfirm')
        if len(password) < 8:
            logger.warning("Password update attempt with password too short")
            raise AppError("Password must be at least 8 characters long", 400)
        if password != password_confirm:
            logger.warning("Password update attempt with mismatched passwords")
            raise AppError("Passwords do not match", 400)

        user.password = password
        user.password_confirm = password_confirm
        user.save()

        logger.info(f"Password updated successfully for user: {user.email}")
        return create_send_token(user, 200, request)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating password: {str(e)}")
        raise AppError(f"Error updating password: {str(e)}", 400)