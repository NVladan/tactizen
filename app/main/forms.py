# app/main/forms.py
from flask_wtf import FlaskForm
from wtforms_sqlalchemy.fields import QuerySelectField
# *** Import IntegerField ***
from wtforms import StringField, TextAreaField, SubmitField, SelectField, HiddenField, IntegerField
# Import NumberRange validator
from wtforms.validators import DataRequired, Length, ValidationError, Regexp, InputRequired, NumberRange
from flask_wtf.file import FileField, FileAllowed
from app.models import User, Country, Region # Import models
from app.extensions import db, cache
from flask_login import current_user
from app.security import InputSanitizer, SQLInjectionPrevention
import re

# --- Helper function to get countries for the form ---
def country_query():
    """Get all active countries for form dropdowns.

    Note: Caching removed because SQLAlchemy Query objects cannot be serialized.
    SQLAlchemy has its own query cache, so this is still efficient.
    """
    return Country.query.filter_by(is_deleted=False).order_by(Country.name)

# --- Define Constants Used in Forms ---
USERNAME_REGEX = r'^[A-Za-z0-9 _-]*$'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Reserved usernames that cannot be used by regular players (anti-scam)
RESERVED_USERNAMES = [
    'admin', 'administrator', 'moderator', 'mod', 'support', 'helpdesk',
    'tactizen', 'system', 'official', 'staff', 'gamemaster', 'gm',
    'developer', 'dev', 'owner', 'founder', 'ceo', 'team',
    'customer_support', 'customersupport', 'help', 'service',
    'security', 'bank', 'treasury', 'government', 'president',
    'npc', 'bot', 'automod', 'root', 'superuser', 'sysadmin'
]

# --- Custom Validators for Security ---
class NoSQLInjection:
    """Validator to check for potential SQL injection attempts."""

    def __init__(self, message=None):
        if not message:
            message = 'Input contains potentially dangerous characters.'
        self.message = message

    def __call__(self, form, field):
        if SQLInjectionPrevention.contains_sql_injection(field.data):
            raise ValidationError(self.message)


class SanitizedInput:
    """Validator that sanitizes input and replaces field data."""

    def __init__(self, sanitizer_func):
        """
        Args:
            sanitizer_func: Function from InputSanitizer to use
        """
        self.sanitizer_func = sanitizer_func

    def __call__(self, form, field):
        if field.data:
            # Sanitize the input
            field.data = self.sanitizer_func(field.data)

# --- Forms ---
class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=4, max=30, message='Username must be between 4 and 30 characters.'),
        Regexp(USERNAME_REGEX, message='Username contains invalid characters.'),
        NoSQLInjection(),
        SanitizedInput(InputSanitizer.sanitize_username)
    ])
    description = TextAreaField('About Me', validators=[
        Length(max=500, message='Description must not exceed 500 characters.'),
        SanitizedInput(InputSanitizer.sanitize_description)
    ])
    avatar = FileField('Update Profile Picture (Optional, Max 2MB)', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Images only!')
    ])
    profile_background = SelectField('Profile Background', choices=[
        ('default', 'Default'),
        ('military', 'Military'),
        ('political', 'Political'),
        ('economic', 'Economic')
    ])
    submit = SubmitField('Save Changes')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        # Skip validation if username hasn't changed (already set and not empty)
        if self.original_username and username.data == self.original_username:
            return

        # Check for reserved usernames (case-insensitive, ignoring spaces/underscores/hyphens)
        if not username.data:
            return  # Let DataRequired handle empty username
        username_normalized = username.data.lower().replace(' ', '').replace('_', '').replace('-', '')
        for reserved in RESERVED_USERNAMES:
            if reserved in username_normalized:
                raise ValidationError('This username is reserved and cannot be used.')

        user = db.session.scalar(db.select(User).where(User.username == username.data, User.is_deleted == False))
        if user is not None:
            raise ValidationError('This username is already taken. Please choose a different one.')

class TrainForm(FlaskForm):
    skill_choice = SelectField('Choose Skill to Train', choices=[
        ('infantry', 'Infantry'), ('armoured', 'Armoured'), ('aviation', 'Aviation')
    ], validators=[DataRequired()])
    submit = SubmitField('Train (Cost: 10 Wellness)')

class StudyForm(FlaskForm):
    skill_choice = SelectField('Choose Skill to Study', choices=[
        ('resource_extraction', 'Resource Extraction'), ('manufacture', 'Manufacture'), ('construction', 'Construction')
    ], validators=[DataRequired()])
    submit = SubmitField('Study (Cost: 10 Wellness)')

class ChooseCitizenshipForm(FlaskForm):
    country = QuerySelectField('Choose Citizenship Country', query_factory=country_query, get_label='name', allow_blank=True, blank_text='-- Select a Country --', validators=[InputRequired(message='Please select a country.')])
    region = SelectField('Choose Starting Region', choices=[], validators=[InputRequired(message='Please select a region.')], validate_choice=False)
    submit = SubmitField('Confirm Citizenship and Start')

class TravelForm(FlaskForm):
    country = QuerySelectField('Destination Country', query_factory=country_query, get_label='name', allow_blank=True, blank_text='-- Select a Country --', validators=[InputRequired(message='Please select a destination country.')])
    region = SelectField('Destination Region', choices=[], validators=[InputRequired(message='Please select a destination region.')], validate_choice=False)
    submit = SubmitField('Move to location (Cost: 1 Gold)')

# --- Market Buy Form (INTEGER) ---
class MarketBuyForm(FlaskForm):
    # *** CHANGED TO IntegerField ***
    quantity = IntegerField('Quantity', validators=[
        InputRequired(message='Please enter a quantity.'),
        NumberRange(
            min=1,
            max=999999,  # Prevent abuse with massive numbers
            message='Quantity must be between 1 and 999,999.'
        )
    ])
    submit = SubmitField('Buy')

# --- Market Sell Form (INTEGER) ---
class MarketSellForm(FlaskForm):
    # *** CHANGED TO IntegerField ***
    quantity = IntegerField('Quantity', validators=[
        InputRequired(message='Please enter a quantity.'),
        NumberRange(
            min=1,
            max=999999,  # Prevent abuse with massive numbers
            message='Quantity must be between 1 and 999,999.'
        )
    ])
    submit = SubmitField('Sell')

# Removed MarketSelectorForm if not used