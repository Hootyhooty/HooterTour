# controllers/errorController.py
from flask import render_template, jsonify, request, redirect, url_for
from Utils.AppError import AppError
import os
import traceback

# Optional: templates for rendering HTML
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

    # Check the Accept header to determine the response type
    if 'text/html' in request.accept_mimetypes and not request.path.startswith('/api/'):
        if error.status_code == 401:
            # Redirect to login page for unauthenticated users
            print("Redirecting to login page due to 401 error")
            return redirect(url_for('view_routes.login'))
        elif error.status_code == 404:
            # Render a custom 404 page
            print("Rendering 404 page")
            return render_template('404.html'), 404
        else:
            # For other errors, render a generic error page if available
            print(f"Rendering generic error page for status {error.status_code}")
            return render_template('error.html', message=str(error), status_code=error.status_code), error.status_code

    # For API requests or non-HTML requests, return JSON
    print("Returning JSON error response")
    if os.getenv("ENV", "development") == "development":
        return jsonify({
            "status": error.status,
            "error": str(err),
            "message": error.message,
            "stack": traceback.format_exc()
        }), error.status_code
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
        if getattr(error, "is_operational", False):
            return jsonify({
                "status": error.status,
                "message": error.message
            }), error.status_code
        return jsonify({
            "status": "error",
            "message": "Something went very wrong!"
        }), 500


def register_handlers(app):
    @app.errorhandler(Exception)
    def handle_exception(e):
        return global_exception_handler(e)

    @app.errorhandler(AppError)
    def handle_app_error(e):
        return global_exception_handler(e)

    @app.errorhandler(404)
    def page_not_found(e):
        if 'text/html' in request.accept_mimetypes and not request.path.startswith('/api/'):
            print("Handling 404 error - rendering 404.html")
            return render_template('404.html'), 404
        print("Handling 404 error - returning JSON")
        return jsonify({
            "status": "error",
            "message": "Resource not found"
        }), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if 'text/html' in request.accept_mimetypes and not request.path.startswith('/api/'):
            print("Handling 500 error - rendering error.html")
            return render_template('error.html', message="Internal Server Error", status_code=500), 500
        print("Handling 500 error - returning JSON")
        return jsonify({
            "status": "error",
            "message": "Internal Server Error"
        }), 500