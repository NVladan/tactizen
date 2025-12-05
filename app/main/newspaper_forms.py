# app/main/newspaper_forms.py
"""Forms for the newspaper system."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, ValidationError
from app.models import Newspaper
from app.extensions import db
from app.security import InputSanitizer, SQLInjectionPrevention
from flask_login import current_user

# --- Define Constants Used in Forms ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_ARTICLE_LENGTH = 10000  # Maximum characters for article content (HTML + image URLs, not base64)

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


# --- Newspaper Forms ---
class CreateNewspaperForm(FlaskForm):
    """Form for creating a new newspaper (costs 5 Gold)."""
    name = StringField('Newspaper Name', validators=[
        DataRequired(message='Newspaper name is required.'),
        Length(min=3, max=100, message='Newspaper name must be between 3 and 100 characters.'),
        NoSQLInjection(),
        SanitizedInput(InputSanitizer.sanitize_username)
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='Description must not exceed 500 characters.'),
        SanitizedInput(InputSanitizer.sanitize_description)
    ])
    avatar = FileField('Newspaper Logo (Optional, Max 2MB)', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Images only!')
    ])
    submit = SubmitField('Create Newspaper (5 Gold)')

    def validate_name(self, name):
        """Ensure newspaper name is unique for this country."""
        if current_user.is_authenticated and current_user.citizenship_id:
            newspaper = db.session.scalar(
                db.select(Newspaper).where(
                    Newspaper.name == name.data,
                    Newspaper.country_id == current_user.citizenship_id,
                    Newspaper.is_deleted == False
                )
            )
            if newspaper is not None:
                raise ValidationError('A newspaper with this name already exists in your country.')


class EditNewspaperForm(FlaskForm):
    """Form for editing an existing newspaper."""
    name = StringField('Newspaper Name', validators=[
        DataRequired(message='Newspaper name is required.'),
        Length(min=3, max=100, message='Newspaper name must be between 3 and 100 characters.'),
        NoSQLInjection(),
        SanitizedInput(InputSanitizer.sanitize_username)
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='Description must not exceed 500 characters.'),
        SanitizedInput(InputSanitizer.sanitize_description)
    ])
    avatar = FileField('Newspaper Logo (Optional, Max 2MB)', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Images only!')
    ])
    submit = SubmitField('Save Changes')

    def __init__(self, original_name, country_id, newspaper_id, *args, **kwargs):
        super(EditNewspaperForm, self).__init__(*args, **kwargs)
        self.original_name = original_name
        self.country_id = country_id
        self.newspaper_id = newspaper_id

    def validate_name(self, name):
        """Ensure newspaper name is unique for this country (excluding current newspaper)."""
        if name.data != self.original_name:
            newspaper = db.session.scalar(
                db.select(Newspaper).where(
                    Newspaper.name == name.data,
                    Newspaper.country_id == self.country_id,
                    Newspaper.id != self.newspaper_id,
                    Newspaper.is_deleted == False
                )
            )
            if newspaper is not None:
                raise ValidationError('A newspaper with this name already exists in your country.')


class WriteArticleForm(FlaskForm):
    """Form for writing a new article."""
    title = StringField('Article Title', validators=[
        DataRequired(message='Article title is required.'),
        Length(min=5, max=200, message='Title must be between 5 and 200 characters.'),
        NoSQLInjection(),
        SanitizedInput(InputSanitizer.sanitize_username)
    ])
    content = TextAreaField('Article Content', validators=[
        DataRequired(message='Article content is required.'),
        Length(max=MAX_ARTICLE_LENGTH, message=f'Content is too long (max {MAX_ARTICLE_LENGTH} characters including HTML).')
    ])
    submit = SubmitField('Publish Article')


class EditArticleForm(FlaskForm):
    """Form for editing an existing article."""
    title = StringField('Article Title', validators=[
        DataRequired(message='Article title is required.'),
        Length(min=5, max=200, message='Title must be between 5 and 200 characters.'),
        NoSQLInjection(),
        SanitizedInput(InputSanitizer.sanitize_username)
    ])
    content = TextAreaField('Article Content', validators=[
        DataRequired(message='Article content is required.'),
        Length(max=MAX_ARTICLE_LENGTH, message=f'Content is too long (max {MAX_ARTICLE_LENGTH} characters including HTML).')
    ])
    submit = SubmitField('Update Article')


class CommentForm(FlaskForm):
    """Form for commenting on an article."""
    content = TextAreaField('Your Comment', validators=[
        DataRequired(message='Comment cannot be empty.'),
        Length(min=1, max=500, message='Comment must not exceed 500 characters.'),
        SanitizedInput(InputSanitizer.sanitize_description)
    ], render_kw={'rows': 3})
    parent_comment_id = HiddenField()  # For nested comments
    submit = SubmitField('Post Comment')
