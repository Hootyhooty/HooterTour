import os
import traceback
from datetime import datetime
from flask import render_template, request, flash, g, redirect, url_for, send_file, current_app
from jinja2 import TemplateNotFound
from Utils.apiFeature import logger
from models.tourModel import Tour, Location
from models.userModel import User, Role
from models.bookingModel import Booking
from models.testimonialModel import Testimonial
from models.reviewModel import Review
from Utils.AppError import AppError
from db import db
from functools import wraps
import random
from io import BytesIO

# Middleware equivalent to alerts
def alerts(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        alert = request.args.get('alert')
        if alert == 'booking':
            flash(
                "Your booking was successful! Please check your email for a confirmation. If your booking doesn't show up here immediately, please come back later.",
                'success'
            )
        return f(*args, **kwargs)
    return decorated_function

def name_to_slug(name):
    """Convert a name to a profile_slug format (lowercase, spaces to hyphens)."""
    if not name:
        return None
    return name.lower().replace(' ', '-').replace('.', '').replace(',', '')

# Route handlers
def home():
    try:
        # Fetch all non-secret tours
        tours = Tour.objects(secret_tour__ne=True)
        print(f"Found {tours.count()} non-secret tours in home")

        # Select up to 4 random tours for the Popular Destinations section
        random_tours = list(tours)
        if random_tours:
            random_tours = random.sample(random_tours, min(4, len(random_tours)))
        else:
            random_tours = []

        # Fetch guides (only active guides or lead-guides)
        guides = list(User.objects(role__in=[Role.GUIDE.value, Role.LEAD_GUIDE.value], active=True))
        print(f"Found {len(guides)} active users with role 'guide' or 'lead-guide' in home")
        if not guides:
            all_roles = User.objects().distinct('role')
            print(f"All roles in database: {all_roles}")

        if guides:
            guides = random.sample(guides, min(3, len(guides)))
            guides = [
                {
                    '_id': str(guide.id),
                    'name': guide.name,
                    'role': guide.role.value if isinstance(guide.role, Role) else guide.role,
                    'photo': f"/api/v1/users/image/{guide.profile_slug}" if guide.photo and guide.photo != 'default.jpg' else '/static/img/users/default.jpg',
                    'profile_slug': guide.profile_slug
                }
                for guide in guides
            ]
        else:
            guides = []
        print(f"Guides data: {guides}")

        # Fetch testimonials
        testimonials = list(Testimonial.objects())
        print(f"Found {len(testimonials)} testimonials in home")
        if testimonials:
            testimonials = random.sample(testimonials, min(5, len(testimonials)))
            testimonials = [testimonial.populate() for testimonial in testimonials]
            testimonials = [
                {
                    '_id': str(testimonial.id),
                    'review': testimonial.review,
                    'name': testimonial.name,
                    'date': testimonial.date.strftime('%Y-%m-%d') if testimonial.date else 'Unknown Date',
                    'user': {
                        '_id': str(testimonial.user.id) if testimonial.user else '',
                        'name': testimonial.user.name if testimonial.user else 'Anonymous',
                        'photo': f"/api/v1/users/image/{testimonial.user.profile_slug}" if testimonial.user and testimonial.user.photo and testimonial.user.photo != 'default.jpg' else '/static/img/users/default.jpg',
                        'profile_slug': testimonial.user.profile_slug if testimonial.user else ''
                    }
                }
                for testimonial in testimonials
            ]
        else:
            testimonials = []
        print(f"Testimonials data: {testimonials}")

        return render_template('index.html', title='All Tours', tours=tours, random_tours=random_tours, guides=guides, testimonials=testimonials)
    except Exception as e:
        print(f"Error in home: {str(e)}")
        raise AppError(str(e), 500)

def get_tour(slug):
    try:
        tour = Tour.objects(slug=slug, secret_tour__ne=True).first()
        if not tour:
            flash('There is no tour with that name.', 'error')
            return render_template('error.html', title='Tour Not Found'), 404
        # Populate guides
        tour = tour.populate_guides()
        # Manually fetch and populate reviews
        reviews = Review.objects(tour=tour.id)
        tour.reviews = []
        for review in reviews:
            populated_review = review.populate()
            if (populated_review.user and
                hasattr(populated_review.user, 'name') and
                hasattr(populated_review.user, 'profile_slug') and
                isinstance(populated_review.created_at, datetime)):
                tour.reviews.append(populated_review)
            else:
                logger.warning(f"Skipping review {review.id} for tour {tour.id}: missing or invalid user data (user: {populated_review.user.id if populated_review.user else None}, created_at: {populated_review.created_at})")
        logger.debug(f"Loaded {len(tour.reviews)} valid reviews for tour {tour.slug}")

        # Validate start_dates
        if not tour.start_dates or not isinstance(tour.start_dates[0], datetime):
            logger.warning(f"Tour {tour.slug} has invalid start_dates: {tour.start_dates}")
            tour.start_dates = [datetime.utcnow()]

        # Validate start_location
        if not tour.start_location or not getattr(tour.start_location, 'description', None):
            logger.warning(f"Tour {tour.slug} has invalid start_location: {tour.start_location}")
            tour.start_location = Location(description='Unknown Location', address='N/A', coordinates=[0.0, 0.0])
        # Ensure start_location has coordinates (should be guaranteed by the model)
        if not tour.start_location.coordinates:
            logger.warning(f"Tour {tour.slug} start_location missing coordinates, setting to default")
            tour.start_location.coordinates = [0.0, 0.0]  # Default to (0,0) if missing

        # Validate locations
        if tour.locations:
            for location in tour.locations:
                if not location.coordinates:
                    logger.warning(f"Tour {tour.slug} location {location.description} missing coordinates, setting to default")
                    location.coordinates = [0.0, 0.0]  # Default to (0,0) if missing
        else:
            logger.warning(f"Tour {tour.slug} has no locations defined")
            tour.locations = []

        # Validate image_cover
        if not tour.image_cover:
            logger.warning(f"Tour {tour.slug} has no image_cover, using default")
            tour.image_cover = 'default-tour-cover.jpg'

        # Verify template exists
        template_path = os.path.join(current_app.template_folder, 'tour_detail.html')
        if not os.path.exists(template_path):
            logger.error(f"Template not found at: {template_path}")
            raise TemplateNotFound('tour_detail.html')

        return render_template('tour_detail.html', title=f'{tour.name} Tour', tour=tour)
    except TemplateNotFound as e:
        logger.error(f"TemplateNotFound in get_tour: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error: Template {e} not found.', 'error')
        return render_template('error.html', title='Template Error'), 500
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_tour: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error loading tour: {e}', 'error')
        return render_template('error.html', title='Error'), 500

def get_login_form():
    return render_template('login.html', title='Log into your account')

def get_account():
    return render_template('account.html', title='Your account')

def get_my_tours():
    try:
        if not hasattr(g, 'user'):
            raise AppError('User not authenticated', 401)
        user_id = g.user.id
        bookings = Booking.objects(user=user_id)
        tour_ids = [str(booking.tour.id) for booking in bookings]
        tours = Tour.objects(id__in=tour_ids)
        return render_template('overview.html', title='My Tours', tours=tours)
    except AppError as e:
        raise e
    except Exception as e:
        raise AppError(str(e), 500)

def dashboard(profile_slug):  # Updated parameter to profile_slug
    try:
        if not hasattr(g, 'user'):
            raise AppError('User not authenticated', 401)
        # Look up user by profile_slug
        user = User.objects(profile_slug=profile_slug, active=True).first()
        if not user:
            raise AppError('User not found', 404)
        # Validate that the user matches the authenticated user
        if str(user.id) != str(g.user.id):
            raise AppError('Unauthorized: You can only access your own dashboard', 403)
        user_data = {
            'id': str(user.id),
            'photo': user.photo,
            'name': user.name,
            'email': user.email,
            'location': getattr(user, 'location', ''),
            'profile_slug': user.profile_slug  # Include profile_slug in case the template needs it
        }
        return render_template('dashboard.html', title='User Dashboard', user=user_data)
    except AppError as e:
        raise e
    except Exception as e:
        raise AppError(str(e), 500)

# controllers/viewController.py
def destination():
    try:
        search_term = request.args.get('search', '').strip()
        tour_slug = request.args.get('tour', '').strip()
        selected_tour = None
        booking = None

        # Fetch selected tour if tour_slug is provided
        if tour_slug:
            selected_tour = Tour.objects(slug=tour_slug, secret_tour__ne=True).first()
            if not selected_tour:
                flash('Selected tour not found.', 'error')
            elif hasattr(g, 'user'):
                # Check for an existing booking for this user and tour
                booking = Booking.objects(user=g.user.id, tour=selected_tour.id).first()

        query = Tour.objects(secret_tour__ne=True)
        if search_term:
            query = query.filter(
                __raw__={
                    '$or': [
                        {'name': {'$regex': search_term, '$options': 'i'}},
                        {'startLocation.description': {'$regex': search_term, '$options': 'i'}}
                    ]
                }
            )
        tours = list(query.order_by('-ratings_average'))
        print(f"Found {len(tours)} non-secret tours")
        for tour in tours:
            print(f"Tour: {tour.name}, ImageCover: {tour.image_cover}, Secret: {tour.secret_tour}")
        if len(tours) == 0:
            print("Warning: No tours available for destination page.")

        return render_template(
            'destination.html',
            title='Destinations',
            tours=tours,
            search_term=search_term,
            selected_tour=selected_tour,
            booking=booking
        )
    except Exception as e:
        print(f"Error in destination: {str(e)}")
        flash(f'Error rendering destination page: {e}', 'error')
        return render_template('error.html'), 500

def serve_image(filename):
    try:
        image_doc = db.get_image_by_filename(filename)
        if not image_doc:
            placeholder_path = os.path.join("static", "img", "placeholder.jpg")
            return send_file(placeholder_path, mimetype='image/jpeg')
        image_data = image_doc["data"]
        return send_file(
            BytesIO(image_data),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        print(f"Error serving image {filename}: {e}")
        placeholder_path = os.path.join("static", "img", "placeholder.jpg")
        return send_file(placeholder_path, mimetype='image/jpeg')

def about():
    try:
        logger.debug("Entering about() function")
        guides = User.objects(role__in=[Role.GUIDE, Role.LEAD_GUIDE], active=True).order_by('-role', 'name')
        logger.debug(f"Found {len(guides)} active users with role 'guide' or 'lead-guide': {[g.name for g in guides]}")

        if not guides:
            all_roles = User.objects().distinct('role')
            logger.debug(f"No guides found. All roles in database: {all_roles}")
            flash('No guides available at the moment.', 'info')
            selected_guides = []
        else:
            selected_guides = []
            for guide in guides:
                if not guide.profile_slug:
                    logger.warning(f"Guide {guide.name} missing profile_slug")
                    continue
                if not guide.name:
                    logger.warning(f"Guide with profile_slug {guide.profile_slug} missing name")
                    continue
                guide_data = {
                    '_id': str(guide.id),
                    'name': guide.name,
                    'role': guide.role.value.replace('-', ' ').title(),
                    'photo': f"/api/v1/users/image/{guide.profile_slug}" if guide.photo and guide.photo != 'default.jpg' else '/static/img/users/default.jpg',
                    'facebook': getattr(guide, 'facebook', ''),
                    'instagram': getattr(guide, 'instagram', ''),
                    'twitter': getattr(guide, 'twitter', ''),
                    'profile_slug': guide.profile_slug
                }
                selected_guides.append(guide_data)
            logger.debug(f"Prepared selected_guides: {selected_guides}")

        logger.debug("Attempting to render about.html")
        response = render_template('about.html', title='About Us', guides=selected_guides)
        logger.debug("Successfully rendered about.html")
        return response
    except TemplateNotFound as e:
        logger.error(f"TemplateNotFound in about: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error: Template {e} not found.', 'error')
        return render_template('error.html', title='Template Error'), 500
    except Exception as e:
        logger.error(f"Error in about function: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error rendering about page: {e}', 'error')
        return render_template('error.html', title='Error'), 500

def contact():
    try:
        return render_template('contact.html')
    except Exception as e:
        flash(f'Error rendering contact page: {e}', 'error')
        return render_template('error.html'), 500

def service():
    try:
        return render_template('service.html')
    except Exception as e:
        flash(f'Error rendering service page: {e}', 'error')
        return render_template('error.html'), 500

def error():
    try:
        return render_template('error.html')
    except Exception as e:
        flash(f'Error rendering 404 page: {e}', 'error')
        return render_template('error.html'), 500

def package():
    try:
        return render_template('package.html')
    except Exception as e:
        flash(f'Error rendering package page: {e}', 'error')
        return render_template('error.html'), 500

def booking():
    try:
        return render_template('booking.html')
    except Exception as e:
        flash(f'Error rendering booking page: {e}', 'error')
        return render_template('error.html'), 500

def team():
    try:
        # Redirect to about page since team functionality is now in about
        return redirect(url_for('view_routes.about'))
    except Exception as e:
        print(f"Error in team redirect: {str(e)}")
        flash(f'Error redirecting to about page: {e}', 'error')
        return render_template('error.html'), 500

def testimonial():
    try:
        testimonials_raw = Testimonial.objects()
        testimonials = []
        for testimonial in testimonials_raw:
            testimonial = testimonial.populate()
            testimonials.append({
                'name': testimonial.name if testimonial.name else 'Anonymous',
                'review': testimonial.review if testimonial.review else 'No review provided',
                'date': testimonial.date.strftime('%Y-%m-%d') if testimonial.date else 'Unknown Date',
                'user': {
                    '_id': str(testimonial.user.id),  # Keep for reference if needed
                    'photo': f"/api/v1/users/image/{testimonial.user.profile_slug}" if testimonial.user and testimonial.user.photo else '/static/img/users/default.jpg'
                } if testimonial.user else {
                    '_id': str(testimonial.id),
                    'photo': 'default.jpg'
                }
            })
        print(f"Found {len(testimonials)} testimonials")
        for t in testimonials:
            print(t)
        return render_template('testimonial.html', title='Testimonials', testimonials=testimonials)
    except Exception as e:
        print(f"Error in testimonial: {str(e)}")
        flash(f'Error rendering testimonial page: {e}', 'error')
        return render_template('error.html'), 500

def guide_profile(name):
    try:
        logger.debug(f"Entering guide_profile with name: {name}")
        guide = User.objects(name=name, role__in=[Role.GUIDE, Role.LEAD_GUIDE], active=True).first()
        if not guide:
            logger.error(f"No active guide or lead-guide found with name: {name}")
            flash('Guide not found.', 'error')
            return render_template('error.html', title='Guide Not Found'), 404
        logger.debug(f"Found guide: {guide.name}, profile_slug: {guide.profile_slug}")

        tours = Tour.objects(guides__in=[guide.id]).order_by('name')
        tour_data = []
        for tour in tours:
            logger.debug(f"Tour {tour.name}: image_cover={tour.image_cover}, slug={tour.slug}")
            tour_data.append({
                'name': tour.name,
                'image_cover': tour.image_cover if tour.image_cover else 'default.jpg',
                'slug': tour.slug  # Added for linking to tour detail page
            })
        logger.debug(f"Found {len(tour_data)} tours for guide {guide.name}: {[t['name'] for t in tour_data]}")
        logger.debug(f"Tour image_cover values: {[t['image_cover'] for t in tour_data]}")
        logger.debug(f"Tour slugs: {[t['slug'] for t in tour_data]}")

        guide_data = {
            'name': guide.name,
            'email': guide.email,
            'role': guide.role.value.replace('-', ' ').title(),
            'photo': f"/api/v1/users/image/{guide.profile_slug}" if guide.photo and guide.photo != 'default.jpg' else '/static/img/users/default.jpg',
            'facebook': getattr(guide, 'facebook', ''),
            'instagram': getattr(guide, 'instagram', ''),
            'twitter': getattr(guide, 'twitter', ''),
            'description': getattr(guide, 'description', ''),
            'profile_slug': guide.profile_slug
        }
        logger.debug(f"Prepared guide_data: {guide_data}")

        logger.debug("Attempting to render guide_profile.html")
        response = render_template('guide_profile.html', title=f"{guide.name}'s Profile", guide=guide_data, tours=tour_data)
        logger.debug("Successfully rendered guide_profile.html")
        return response
    except TemplateNotFound as e:
        logger.error(f"TemplateNotFound in guide_profile for name {name}: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error: Template {e} not found.', 'error')
        return render_template('error.html', title='Template Error'), 500
    except Exception as e:
        logger.error(f"Error in guide_profile for name {name}: {str(e)}\n{traceback.format_exc()}")
        flash(f'Error rendering guide profile: {e}', 'error')
        return render_template('error.html', title='Error'), 500

def payment(tour_id):
    try:
        tour = Tour.objects(id=tour_id, secret_tour__ne=True).first()
        if not tour:
            flash('Tour not found.', 'error')
            return render_template('error.html', title='Tour Not Found'), 404

        stripe_public_key = os.getenv('STRIPE_PUBLIC_KEY')
        stripe_webhook = os.getenv('STRIPE_WEBHOOK')
        if not stripe_public_key:
            logger.error("Stripe public key not configured")
            raise AppError("Payment configuration error", 500)

        return render_template('payment.html', title=f'Payment for {tour.name}', tour=tour,
                               stripe_public_key=stripe_public_key, stripe_webhook=stripe_webhook
                               )
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in payment: {str(e)}")
        flash(f'Error loading payment page: {e}', 'error')
        return render_template('error.html', title='Error'), 500

def booking_summary(booking_id):
    try:
        if not hasattr(g, 'user'):
            raise AppError('User not authenticated', 401)

        booking = Booking.objects(id=booking_id).first()
        if not booking:
            raise AppError('Booking not found', 404)

        if str(booking.user.id) != str(g.user.id):
            raise AppError('Unauthorized: You can only view your own bookings', 403)

        tour = Tour.objects(id=booking.tour.id).first()
        if not tour:
            raise AppError('Associated tour not found', 404)

        user = User.objects(id=booking.user.id).first()
        if not user:
            raise AppError('Associated user not found', 404)

        return render_template('booking_summary.html', title='Booking Summary', booking=booking, tour=tour, user=user)
    except AppError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in booking_summary: {str(e)}")
        flash(f'Error loading booking summary: {e}', 'error')
        return render_template('error.html', title='Error'), 500