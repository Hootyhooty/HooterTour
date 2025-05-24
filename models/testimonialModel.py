from mongoengine import Document, StringField, DateTimeField, ReferenceField, signals
from datetime import datetime
from models.userModel import User


class Testimonial(Document):
    """
    A MongoDB document representing a Testimonial using mongoengine.
    """

    # Fields
    review = StringField(
        required=True,
        help_text="Testimonial text cannot be empty!"
    )
    name = StringField(
        required=True,
        max_length=50,
        help_text="Name of the user leaving the testimonial"
    )
    date = DateTimeField(
        default=datetime.utcnow
    )
    user = ReferenceField(
        User,
        required=True,
        help_text="Testimonial must belong to a user"
    )

    # Meta configuration
    meta = {
        'collection': 'testimonials',  # Name of the MongoDB collection
        'indexes': [
            {'fields': ['user'], 'unique': True}  # Unique index on user
        ],
        'auto_create_index': True
    }

    # Pre-find hook to modify query
    @classmethod
    def pre_find(cls, query):
        """
        Modify the query to populate user (selecting only name and photo).
        """
        return query

    def populate(self):
        """
        Manually populate user fields after querying.
        """
        if self.user and isinstance(self.user, ReferenceField):
            self.user = User.objects(id=self.user.id).only('name', 'photo').first()
        return self


# Helper to apply population
def get_testimonials():
    testimonials = Testimonial.objects(__raw__={})
    return [testimonial.populate() for testimonial in testimonials]

