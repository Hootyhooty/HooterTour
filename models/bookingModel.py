from mongoengine import Document, ReferenceField, FloatField, DateTimeField, \
    BooleanField, signals, StringField
from datetime import datetime
from typing import Optional

# Assuming these are defined in their respective files
from models.tourModel import Tour
from models.userModel import User


class Booking(Document):
    tour = ReferenceField(
        Tour,
        required=True,
        help_text="Booking must belong to a Tour!"
    )
    user = ReferenceField(
        User,
        required=True,
        help_text="Booking must belong to a User!"
    )
    price = FloatField(
        required=True,
        help_text="Booking must have a price."
    )
    tour_slug = StringField(
        required=False,
        help_text="Slug of the booked tour for reference."
    )
    created_at = DateTimeField(
        default=datetime.utcnow
    )
    paid = BooleanField(
        default=True
    )

    meta = {
        'collection': 'bookings',
        'indexes': [
            'tour',
            'user',
            'tour_slug'
        ],
        'auto_create_index': True
    }

    # Pre-find hook (equivalent to Mongoose pre(/^find/))
    @classmethod
    def pre_find(cls, query):
        """
        Modify the query to populate user and tour (selecting only tour name).
        Note: mongoengine doesn't auto-populate; this is a manual step.
        """
        # Return raw query with filters; population is handled in the query logic
        return query

    def populate(self):
        """
        Manually populate user and tour fields after querying.
        """
        # Populate user (all fields)
        if self.user and isinstance(self.user, ReferenceField):
            self.user = User.objects(id=self.user.id).first()

        # Populate tour (only name field)
        if self.tour and isinstance(self.tour, ReferenceField):
            self.tour = Tour.objects(id=self.tour.id).only('name').first()

        return self


# Example query wrapper to apply population
def get_bookings():
    bookings = Booking.objects(__raw__={})
    return [booking.populate() for booking in bookings]