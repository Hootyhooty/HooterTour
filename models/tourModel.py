from mongoengine import Document, StringField, IntField, FloatField, ListField, \
    ReferenceField, DateTimeField, BooleanField, EmbeddedDocument, \
    EmbeddedDocumentField, ValidationError, QuerySet, ObjectIdField
from mongoengine import signals
from slugify import slugify
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dateutil import parser

class Location(EmbeddedDocument):
    _id = ObjectIdField(required=False)
    type = StringField(default="Point", choices=["Point"], required=True)
    coordinates = ListField(FloatField(), required=True)
    address = StringField()
    description = StringField()
    day = IntField(min_value=1)

    def to_json(self) -> Dict[str, Any]:
        return {
            'id': str(self._id) if self._id else None,
            'type': self.type,
            'coordinates': self.coordinates,
            'address': self.address,
            'description': self.description,
            'day': self.day
        }

class TourQuerySet(QuerySet):
    def __init__(self, document, collection):
        super().__init__(document, collection)
        self._initial_query = {'secretTour': {'$ne': True}}
        self._bypass_secret_filter = False

    def bypass_secret_filter(self):
        """Bypass the secretTour filter for this query."""
        self._bypass_secret_filter = True
        return self

    def get_filter(self):
        """Override to conditionally apply the secretTour filter."""
        if self._bypass_secret_filter:
            return {}
        return self._initial_query

    def _transform_query(self, **kwargs):
        transformed = {}
        field_map = {
            'ratings_average': 'ratingsAverage',
            'ratings_quantity': 'ratingsQuantity',
            'max_group_size': 'maxGroupSize',
            'start_location': 'startLocation',
            'start_dates': 'startDates',
            'secret_tour': 'secretTour',
            'image_cover': 'imageCover',
            'price': 'price',
            'difficulty': 'difficulty',
            'name': 'name',
            'duration': 'duration',
            'summary': 'summary',
            'description': 'description',
            'images': 'images',
            'created_at': 'createdAt',
            'guides': 'guides',
            'slug': 'slug',
            'price_discount': 'priceDiscount',
            'locations': 'locations'
        }
        for key, value in kwargs.items():
            parts = key.split('__')
            base_key = parts[0]
            operator = '__' + parts[1] if len(parts) > 1 else ''
            new_key = field_map.get(base_key, base_key) + operator
            transformed[new_key] = value
        return transformed

class Tour(Document):
    name = StringField(required=True, unique=True, max_length=40, min_length=10, db_field='name')
    slug = StringField(unique=True, db_field='slug')
    duration = IntField(required=True, min_value=1, db_field='duration')
    max_group_size = IntField(required=True, min_value=1, db_field='maxGroupSize')
    difficulty = StringField(required=True, choices=["easy", "medium", "difficult"], db_field='difficulty')
    ratings_average = FloatField(default=4.5, min_value=1.0, max_value=5.0, db_field='ratingsAverage')
    ratings_quantity = IntField(default=0, min_value=0, db_field='ratingsQuantity')
    price = IntField(required=True, min_value=1, db_field='price')
    price_discount = IntField(min_value=0, db_field='priceDiscount')
    summary = StringField(required=False, db_field='summary')
    description = StringField(db_field='description')
    image_cover = StringField(required=False, db_field='imageCover')
    images = ListField(StringField(), db_field='images')
    created_at = DateTimeField(default=datetime.utcnow, db_field='createdAt')
    start_dates = ListField(DateTimeField(), db_field='startDates')
    secret_tour = BooleanField(default=False, db_field='secretTour')
    start_location = EmbeddedDocumentField(Location, db_field='startLocation')
    locations = ListField(EmbeddedDocumentField(Location), db_field='locations')
    guides = ListField(ReferenceField('User'), db_field='guides')
    stripe_payment_link = StringField(db_field='paymentLink')

    meta = {
        'collection': 'tours',
        'queryset_class': TourQuerySet,
        'indexes': [
            'price',
            '-ratings_average',
            'slug'
        ]
    }

    @property
    def duration_weeks(self) -> Optional[float]:
        return self.duration / 7 if self.duration else None

    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        if not document.slug:
            base_slug = slugify(document.name, lowercase=True)
            slug = base_slug
            suffix = 1
            while cls.objects(slug=slug).first() is not None:
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            document.slug = slug

    def clean(self):
        if self.price_discount is not None and self.price_discount >= self.price:
            raise ValidationError("Discount price should be below regular price")
        if self.start_location and (len(self.start_location.coordinates) != 2 or
                                    not -180 <= self.start_location.coordinates[0] <= 180 or
                                    not -90 <= self.start_location.coordinates[1] <= 90):
            raise ValidationError("Start location coordinates must be [longitude, latitude] with valid ranges")
        if self.locations:
            for loc in self.locations:
                if len(loc.coordinates) != 2 or \
                   not -180 <= loc.coordinates[0] <= 180 or \
                   not -90 <= loc.coordinates[1] <= 90:
                    raise ValidationError("Location coordinates must be [longitude, latitude] with valid ranges")

    def to_json(self) -> Dict[str, Any]:
        start_dates = []
        if self.start_dates:
            for date in self.start_dates:
                if isinstance(date, str):
                    dt = parser.isoparse(date)
                    start_dates.append(dt.isoformat())
                elif isinstance(date, datetime):
                    start_dates.append(date.isoformat())
                else:
                    start_dates.append(str(date))
        created_at = self.created_at
        if isinstance(created_at, str):
            created_at = parser.isoparse(created_at)

        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'duration': self.duration,
            'maxGroupSize': self.max_group_size,
            'difficulty': self.difficulty,
            'ratingsAverage': round(self.ratings_average, 1) if self.ratings_average is not None else None,
            'ratingsQuantity': self.ratings_quantity,
            'price': self.price,
            'priceDiscount': self.price_discount,
            'summary': self.summary,
            'description': self.description,
            'imageCover': self.image_cover,
            'images': self.images,
            'createdAt': created_at.isoformat() if created_at else None,
            'startDates': start_dates,
            'secretTour': self.secret_tour,
            'startLocation': self.start_location.to_json() if self.start_location else None,
            'locations': [loc.to_json() for loc in self.locations] if self.locations else [],
            'guides': [str(guide.id) for guide in self.guides] if self.guides else [],
            'durationWeeks': self.duration_weeks
        }

    def populate_guides(self) -> 'Tour':
        if self.guides:
            self.guides = [guide for guide in self.guides]
        return self

signals.pre_save.connect(Tour.pre_save, sender=Tour)