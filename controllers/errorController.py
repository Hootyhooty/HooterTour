from flask import render_template, jsonify, request
from Utils.AppError import AppError
import os
import traceback

# Optional: Templates for rendering HTML
templates = None
if os.path.exists("templates"):
    from flask import Flask
    app = Flask(__name__)  # Temporary for template setup
    templates = app.jinja_env

def handle_cast_error_db(err):
    message = f"Invalid {err.path}: {err.value}"
    return AppError(message, 400)

def handle_duplicate_fields_db(err):
    value = "duplicate_value"  # Simplify; adjust based on your DB
    message = f"Duplicate field value: {value}. Please use another value!"
    return AppError(message, 400)

def handle_validation_error_db(err):
    errors = [error["msg"] for error in err.errors]  # Adjust based on your validation lib
    message = f"Invalid input data. {' '.join(errors)}"
    return AppError(message, 400)

def handle_jwt_error():
    return AppError("Invalid token. Please log in again!", 401)

def handle_jwt_expired_error():
    return AppError("Your token has expired! Please log in again!", 401)

def send_error_dev(err, request):
    # A) API
    if request.path.startswith("/api"):
        return jsonify({
            "status": err.status,
            "error": str(err),
            "message": err.message,
            "stack": traceback.format_exc()
        }), err.status_code
    # B) Rendered Website
    print(f"ERROR 💥: {err}")
    return render_template(
        "error.html",
        title="Something went wrong!",
        msg=err.message
    ), err.status_code

def send_error_prod(err, request):
    # A) API
    if request.path.startswith("/api"):
        if getattr(err, "is_operational", False):
            return jsonify({
                "status": err.status,
                "message": err.message
            }), err.status_code
        # Unknown error
        print(f"ERROR 💥: {err}")
        return jsonify({
            "status": "error",
            "message": "Something went very wrong!"
        }), 500
    # B) Rendered Website
    if getattr(err, "is_operational", False):
        return render_template(
            "error.html",
            title="Something went wrong!",
            msg=err.message
        ), err.status_code
    # Unknown error
    print(f"ERROR 💥: {err}")
    return render_template(
        "error.html",
        title="Something went wrong!",
        msg="Please try again later."
    ), err.status_code

def global_exception_handler(err):
    status_code = getattr(err, "status_code", 500)
    status = getattr(err, "status", "error")
    message = getattr(err, "message", str(err))

    error = err if isinstance(err, AppError) else AppError(message, status_code)
    error.status_code = status_code
    error.status = status
    error.message = message

    if os.getenv("ENV", "development") == "development":
        return send_error_dev(error, request)
    else:
        if getattr(err, "name", "") == "CastError":
            error = handle_cast_error_db(err)
        elif getattr(err, "code", None) == 11000:
            error = handle_duplicate_fields_db(err)
        elif getattr(err, "name", "") == "ValidationError":
            error = handle_validation_error_db(err)
        elif getattr(err, "name", "") == "JsonWebTokenError":
            error = handle_jwt_error()
        elif getattr(err, "name", "") == "TokenExpiredError":
            error = handle_jwt_expired_error()
        return send_error_prod(error, request)

# Note: Flask requires the request object to be passed, so this needs adjustment
# Define a proper error handler with request context
def register_handlers(app):
    @app.errorhandler(Exception)
    def handle_exception(e):
        return global_exception_handler(e)

    @app.errorhandler(AppError)
    def handle_app_error(e):
        return global_exception_handler(e)

