# commands/update_ratings.py
import click
from flask.cli import with_appcontext
from models.tourModel import Tour
from models.reviewModel import Review
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command(name='update-ratings')
@with_appcontext
def update_tour_ratings():
    try:
        # Get all tours
        tours = Tour.objects()
        total_tours = len(tours)
        logger.info(f"Found {total_tours} tours to process")

        for index, tour in enumerate(tours, 1):
            logger.info(f"Processing tour {index}/{total_tours}: {tour.name} (slug: {tour.slug})")

            # Find all reviews for this tour
            reviews = Review.objects(tour=tour.id)
            review_count = len(reviews)

            if review_count == 0:
                # No reviews: reset to default values
                new_ratings_quantity = 0
                new_ratings_average = 4.5  # Default as per model
                logger.info(f"Tour {tour.name} has no reviews. Setting ratings_quantity=0, ratings_average=4.5")
            else:
                # Calculate average rating
                total_rating = sum(review.rating for review in reviews)
                new_ratings_average = round(total_rating / review_count, 1)  # Round to 1 decimal place
                new_ratings_quantity = review_count
                logger.info(f"Tour {tour.name} has {review_count} reviews. New ratings_average={new_ratings_average}")

            # Update the tour only if values have changed
            if (tour.ratings_quantity != new_ratings_quantity or
                tour.ratings_average != new_ratings_average):
                tour.ratings_quantity = new_ratings_quantity
                tour.ratings_average = new_ratings_average
                tour.save()
                logger.info(f"Updated tour {tour.name}: ratings_average={tour.ratings_average}, ratings_quantity={tour.ratings_quantity}")
            else:
                logger.info(f"No update needed for tour {tour.name}")

    except Exception as e:
        logger.error(f"Error updating tour ratings: {str(e)}")
        raise

def register_commands(app):
    app.cli.add_command(update_tour_ratings)

