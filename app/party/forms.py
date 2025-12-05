# app/party/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError
from slugify import slugify

from app.extensions import db
from app.models import PoliticalParty


class CreatePartyForm(FlaskForm):
    """Form for creating a new political party."""
    name = StringField(
        'Party Name',
        validators=[
            DataRequired(message='Party name is required'),
            Length(min=3, max=50, message='Party name must be between 3 and 50 characters')
        ],
        render_kw={'placeholder': 'Enter party name'}
    )
    description = TextAreaField(
        'Party Description',
        validators=[
            Length(max=500, message='Description cannot exceed 500 characters')
        ],
        render_kw={'placeholder': 'Describe your party\'s goals and values (optional)', 'rows': 5}
    )
    submit = SubmitField('Create Party (5 Gold)')

    def __init__(self, user=None, *args, **kwargs):
        super(CreatePartyForm, self).__init__(*args, **kwargs)
        self.user = user

    def validate_name(self, field):
        """Check if party name is unique in the user's country."""
        if not self.user or not self.user.citizenship_id:
            raise ValidationError('You must be a citizen of a country to create a party.')

        # Check for duplicate party name in same country
        slug = slugify(field.data)
        existing_party = db.session.scalar(
            db.select(PoliticalParty)
            .where(PoliticalParty.country_id == self.user.citizenship_id)
            .where(PoliticalParty.slug == slug)
            .where(PoliticalParty.is_deleted == False)
        )

        if existing_party:
            raise ValidationError('A party with this name already exists in your country.')


class EditPartyForm(FlaskForm):
    """Form for editing party description and logo (politics only)."""
    description = TextAreaField(
        'Party Description',
        validators=[
            Length(max=500, message='Description cannot exceed 500 characters')
        ],
        render_kw={'placeholder': 'Describe your party\'s goals and values', 'rows': 5}
    )
    logo = FileField(
        'Party Logo',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png'], 'Only JPG and PNG images are allowed')
        ]
    )
    submit = SubmitField('Save Changes')


class AnnounceCandidacyForm(FlaskForm):
    """Form for announcing candidacy in party politics election."""
    submit = SubmitField('Announce Candidacy')


class VoteForm(FlaskForm):
    """Form for voting in party politics election."""
    candidate_id = SelectField(
        'Select Candidate',
        coerce=int,
        validators=[DataRequired(message='Please select a candidate')]
    )
    submit = SubmitField('Cast Vote')

    def __init__(self, candidates=None, *args, **kwargs):
        super(VoteForm, self).__init__(*args, **kwargs)
        if candidates:
            self.candidate_id.choices = [
                (c.user_id, f"{c.user.username} (Level {c.user.level})")
                for c in candidates
            ]
