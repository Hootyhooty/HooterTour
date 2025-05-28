from mongoengine import Document, EmailField, StringField, BooleanField, DateTimeField, EnumField
from mongoengine import ValidationError
from bcrypt import hashpw, gensalt, checkpw
import hashlib
import secrets
from datetime import datetime, timedelta
from enum import Enum
from hashids import Hashids
import os

# Configure Hashids
HASHIDS_SALT = os.getenv('HASHIDS_SALT', 'default-salt')
HASHIDS_MIN_LENGTH = int(os.getenv('HASHIDS_MIN_LENGTH', 16))
HASHIDS_ALPHABET = os.getenv('HASHIDS_ALPHABET', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH, alphabet=HASHIDS_ALPHABET)

class Role(Enum):
    USER = "user"
    GUIDE = "guide"
    LEAD_GUIDE = "lead-guide"
    ADMIN = "admin"

class User(Document):
    name = StringField(required=True, max_length=50, help_text="Please tell us your name!")
    email = EmailField(required=True, unique=True, help_text="Please provide your email")
    photo = StringField(default="default.jpg")
    role = EnumField(Role, default=Role.USER)
    password = StringField(required=True, min_length=8, help_text="Please provide a password with at least 8 characters")
    password_confirm = StringField(required=False, help_text="Please confirm your password")
    password_changed_at = DateTimeField()
    password_reset_token = StringField()
    password_reset_expires = DateTimeField()
    active = BooleanField(default=True)
    location = StringField(max_length=100, required=False, help_text="User's location (e.g., New York, USA)")
    facebook = StringField(required=False, help_text="User's Facebook profile URL")
    instagram = StringField(required=False, help_text="User's Instagram profile URL")
    twitter = StringField(required=False, help_text="User's Twitter profile URL")
    description = StringField(max_length=500, required=False, help_text="A brief description of the user")
    profile_slug = StringField(unique=True, required=True, max_length=100, help_text="Unique HashID-based identifier for the user")

    meta = {
        'collection': 'users',
        'indexes': ['email', 'password_reset_token', 'profile_slug']
    }

    def generate_profile_slug(self):
        """
        Generate a unique profile slug as a HashID based on ObjectId.
        """
        if not self.id:
            raise ValidationError("Cannot generate profile slug before ObjectId is assigned")
        unique_int = int(self.id.generation_time.timestamp() * 1000) + int(str(self.id)[18:], 16)
        slug = hashids.encode(unique_int)
        existing_user = User.objects(profile_slug=slug).first()
        if existing_user and str(existing_user.id) != str(self.id):
            raise ValidationError(f"HashID collision for slug {slug}")
        return slug

    def pre_save(self):
        if self.password:
            if isinstance(self.password, str):
                self.password = hashpw(self.password.encode('utf-8'), gensalt(12)).decode('utf-8')
            else:
                raise ValidationError("Password must be a string")

        if self.id and self.password:
            self.password_changed_at = datetime.utcnow() - timedelta(seconds=1)

        # Generate profile_slug after ObjectId is assigned
        if self.id and not self.profile_slug:
            self.profile_slug = self.generate_profile_slug()

    def clean(self):
        if self.password and self.password_confirm:
            if self.password != self.password_confirm:
                raise ValidationError("Passwords do not match!")
        self.password_confirm = None

    def save(self, *args, **kwargs):
        # If this is a new document (no ObjectId yet), save without validation to generate ObjectId
        if not self.id:
            # First save: skip validation to generate ObjectId
            super().save(*args, validate=False, **kwargs)
            # Generate profile_slug now that we have an ObjectId
            self.pre_save()
            # Second save: run validation to ensure all fields (including profile_slug) are correct
            super().save(*args, **kwargs)
        else:
            # For existing documents, run validation as normal
            self.clean()
            self.pre_save()
            super().save(*args, **kwargs)

    def correct_password(self, candidate_password: str, user_password: str) -> bool:
        return checkpw(candidate_password.encode('utf-8'), user_password.encode('utf-8'))

    def changed_password_after(self, jwt_timestamp: int) -> bool:
        if self.password_changed_at:
            changed_timestamp = int(self.password_changed_at.timestamp())
            return jwt_timestamp < changed_timestamp
        return False

    def create_password_reset_token(self) -> str:
        reset_token = secrets.token_hex(32)
        self.password_reset_token = hashlib.sha256(reset_token.encode('utf-8')).hexdigest()
        self.password_reset_expires = datetime.utcnow() + timedelta(minutes=10)
        return reset_token

    def to_json(self) -> dict:
        return {
            'id': str(self.id),
            'name': self.name,
            'email': self.email,
            'role': self.role.value,
            'photo': self.photo,
            'location': getattr(self, 'location', None),
            'facebook': getattr(self, 'facebook', None),
            'instagram': getattr(self, 'instagram', None),
            'twitter': getattr(self, 'twitter', None),
            'description': getattr(self, 'description', None),
            'active': self.active,
            'profile_slug': self.profile_slug
        }