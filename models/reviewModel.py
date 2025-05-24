from mongoengine import Document, StringField, FloatField, DateTimeField, \
    ReferenceField, signals
from datetime import datetime
from typing import Optional, List, Dict, Any
from models.tourModel import Tour
from models.userModel import User


class Review(Document):
    """
    A MongoDB document representing a Review using mongoengine.
    """

    # Fields
    review = StringField(
        required=True,
        help_text="Review can not be empty!"
    )
    rating = FloatField(
        min_value=1,
        max_value=5
    )
    created_at = DateTimeField(
        default=datetime.utcnow
    )
    tour = ReferenceField(
        Tour,
        required=True,
        help_text="Review must belong to a tour."
    )
    user = ReferenceField(
        User,
        required=True,
        help_text="Review must belong to a user"
    )

    # Meta configuration
    meta = {
        'collection': 'reviews',  # Name of the MongoDB collection
        'indexes': [
            {'fields': ['tour', 'user'], 'unique': True}  # Unique index on tour and user
        ],
        'auto_create_index': True
    }

    # Pre-find hook (equivalent to Mongoose pre(/^find/))
    @classmethod
    def pre_find(cls, query):
        """
        Modify the query to populate user (selecting only name and photo).
        Note: mongoengine doesn't auto-populate; this is a manual step.
        """
        return query

    def populate(self):
        """
        Manually populate user fields after querying.
        """
        # Populate user (only name and photo fields)
        if self.user and isinstance(self.user, ReferenceField):
            self.user = User.objects(id=self.user.id).only('name', 'photo').first()
        # Note: We don't populate tour as per the commented-out Mongoose code
        return self

    # Static method to calculate average ratings
    @staticmethod
    def calc_average_ratings(tour_id: str) -> None:
        """
        Calculate the average rating and quantity for a tour, then update the tour.
        Equivalent to Mongoose reviewSchema.statics.calcAverageRatings.
        """
        from mongoengine import Q

        # Aggregate to calculate stats
        stats = Review.objects(tour=tour_id).aggregate([
            {"$match": {"tour": {"$eq": tour_id}}},  # Match reviews for this tour
            {
                "$group": {
                    "_id": "$tour",
                    "nRating": {"$sum": 1},  # Count number of reviews
                    "avgRating": {"$avg": "$rating"}  # Average rating
                }
            }
        ])

        # Convert stats to list for processing
        stats = list(stats)

        if stats:
            # Update the tour with new ratings
            Tour.objects(id=tour_id).update_one(
                ratings_quantity=stats[0]['nRating'],
                ratings_average=stats[0]['avgRating']
            )
        else:
            # Reset to defaults if no reviews exist
            Tour.objects(id=tour_id).update_one(
                ratings_quantity=0,
                ratings_average=4.5
            )

    # Post-save hook (equivalent to Mongoose post('save'))
    @classmethod
    def post_save(cls, sender, document, **kwargs):
        """
        Calculate average ratings after saving a review.
        """
        cls.calc_average_ratings(str(document.tour.id))

    # Pre-findOneAnd hook (equivalent to Mongoose pre(/^findOneAnd/))
    @classmethod
    def pre_find_one_and(cls, query):
        """
        Store the current review document before an update or delete operation.
        Note: mongoengine doesn't have a direct equivalent; this is a manual step.
        """
        document = cls.objects(__raw__=query).first()
        cls._temp_review = document  # Store temporarily for post-hook
        return query

    # Post-findOneAnd hook (equivalent to Mongoose post(/^findOneAnd/))
    @classmethod
    def post_find_one_and(cls, sender, document, **kwargs):
        """
        Calculate average ratings after an update or delete operation.
        """
        if hasattr(cls, '_temp_review') and cls._temp_review:
            cls.calc_average_ratings(str(cls._temp_review.tour.id))
            cls._temp_review = None  # Clear temporary storage


# Connect hooks
signals.post_save.connect(Review.post_save, sender=Review)


# Helper to apply population
def get_reviews():
    reviews = Review.objects(__raw__={})
    return [review.populate() for review in reviews]


if __name__ == "__main__":
    from mongoengine import connect

    connect('mydb', host='mongodb://localhost:27017/')
    # Example instantiation (for testing)
    tour = Tour.objects.first()
    user = User.objects.first()
    review = Review(
        review="Amazing tour experience!",
        rating=4.8,
        tour=tour,
        user=user
    )
    review.save()
    print(review.to_json())