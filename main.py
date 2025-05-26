from datetime import datetime
from flask import Flask, g, render_template, request, abort, send_file
from flask_bootstrap import Bootstrap
from dotenv import load_dotenv
import io
import os
import sys
import signal

from hashids import Hashids

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = 'public/img/users'
app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')

# Initialize Bootstrap
Bootstrap(app)

# Import db after app initialization to avoid circular imports
from db import db

# Global flag to track server state
server_running = False

# Error handling for uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    print(f"UNCAUGHT EXCEPTION! {exc_type.__name__}: {exc_value}", file=sys.stderr)
    if server_running:
        print("Shutting down gracefully...")
        shutdown_server()
    sys.exit(1)

sys.excepthook = handle_exception

# Initialize Hashids
HASHIDS_SALT = os.getenv('HASHIDS_SALT', 'default-salt')
HASHIDS_MIN_LENGTH = int(os.getenv('HASHIDS_MIN_LENGTH', 16))
HASHIDS_ALPHABET = os.getenv('HASHIDS_ALPHABET', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH, alphabet=HASHIDS_ALPHABET)

# Define datetimeformat filter
def datetimeformat(value, format='%B %d, %Y'):
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

# Define hashid filter
def hashid_encode(value):
    try:
        # Convert ObjectId (hex string) to integer
        int_value = int(str(value), 16)
        return hashids.encode(int_value)
    except Exception as e:
        print(f"Error encoding hashid: {e}")
        return value

# Register the filter with Jinja2
app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['hashid'] = hashid_encode


# Graceful shutdown handler
def shutdown_server():
    global server_running
    if server_running:
        print("Shutting down gracefully...")
        if db.client:
            print("Closing MongoDB connection...")
            db.client.close()
        server_running = False
        sys.exit(0)
    else:
        print("Server not running, no need to shut down.")

# Signal handlers for SIGTERM and SIGINT
def signal_handler(sig, frame):
    print(f"{signal.Signals(sig).name} received. Shutting down gracefully...")
    shutdown_server()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Import controllers and routes after app initialization to avoid circular imports
from controllers.authController import signup, login
from controllers.bookingController import webhook_checkout
from controllers.viewController import get_login_form
from routes.viewRoutes import view_routes
from routes.userRoutes import user_routes
from routes.tourRoutes import tour_routes
from routes.reviewRoutes import review_routes
from routes.bookingRoutes import booking_routes
from routes.testimonialRoutes import testimonial_routes
from controllers.errorController import register_handlers
from controllers.userController import serve_user_image

# Register blueprints
app.register_blueprint(view_routes)
app.register_blueprint(user_routes)
app.register_blueprint(tour_routes)
app.register_blueprint(review_routes)
app.register_blueprint(booking_routes)
app.register_blueprint(testimonial_routes)

# Combined /login route
@app.route('/login', methods=['GET', 'POST'])
def login_route():
    if request.method == 'GET':
        return get_login_form()
    return login()

# Register auth routes
app.route('/signup', methods=['GET', 'POST'])(signup)
app.route('/webhook-checkout', methods=['POST'])(webhook_checkout)

register_handlers(app)

# Image serving routes
@app.route('/images/user_imgs/<filename>')
def serve_user_image_from_collection(filename):
    try:
        collection = db.get_user_imgs_collection()
        image_doc = collection.find_one({"filename": filename})
        if not image_doc:
            abort(404, description=f"Image {filename} not found in user_imgs collection")

        image_data = image_doc['data']
        mime_type = 'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
        return send_file(
            io.BytesIO(image_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        abort(500, description=f"Error serving image {filename} from user_imgs: {str(e)}")

@app.route('/images/imgs/<filename>')
def serve_static_image(filename):
    try:
        collection = db.get_imgs_collection()
        image_doc = collection.find_one({"filename": filename})
        if not image_doc:
            placeholder_path = os.path.join("static", "img", "placeholder.jpg")
            if os.path.exists(placeholder_path):
                return send_file(placeholder_path, mimetype='image/jpeg')
            abort(404, description=f"Image {filename} not found in imgs collection and no placeholder available")

        image_data = image_doc['data']
        mime_type = 'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
        return send_file(
            io.BytesIO(image_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        abort(500, description=f"Error serving image {filename} from imgs: {str(e)}")

@app.route('/images/users/<user_id>')
def serve_user_image_route(user_id):
    return serve_user_image(user_id)

# Server startup
if __name__ == "__main__":
    print("Starting application...")
    try:
        if db.client is None:
            print("Database client is None, connecting...")
            db.connect()
        print("Pinging MongoDB server...")
        db.client.admin.command('ping')
        print("Confirmed database connection before importing data.")
    except Exception as e:
        print(f"Failed to establish database connection: {e}")
        shutdown_server()

    print("Attempting to import initial data...")
    try:
        from Data.Import_data import DataImporter
        print("Creating DataImporter instance...")
        importer = DataImporter()
        print("Calling import_all_data...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        importer.import_all_data(
            users_file=os.path.join(base_dir, 'data', 'users.json'),
            tours_file=os.path.join(base_dir, 'data', 'tours.json'),
            reviews_file=os.path.join(base_dir, 'data', 'reviews.json')
        )
    except Exception as e:
        print(f"Failed to import initial data: {e}")
        print("Shutting down due to import failure...")
        shutdown_server()
        raise

    print("Attempting to upload images to user_imgs and imgs collections...")
    try:
        from upload_images import upload_images
        from upload_tour_images import upload_tour_images
        upload_images()
        upload_tour_images()
    except Exception as e:
        print(f"Failed to upload images: {e}")
        print("Continuing with server startup despite image upload failure...")

    port = int(os.getenv('PORT', 5000))
    server_running = True
    print(f"App running on port {port}...")
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Shutting down gracefully...")
        shutdown_server()
    except Exception as e:
        print(f"Error starting server: {e}")
        shutdown_server()