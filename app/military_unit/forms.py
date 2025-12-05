# app/military_unit/forms.py
"""
Forms for Military Unit operations.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField, DecimalField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional
from decimal import Decimal

from app.extensions import db
from app.models import MilitaryUnit


class CreateUnitForm(FlaskForm):
    """Form for creating a new military unit."""
    name = StringField(
        'Unit Name',
        validators=[
            DataRequired(message='Unit name is required'),
            Length(min=3, max=100, message='Unit name must be between 3 and 100 characters')
        ],
        render_kw={'placeholder': 'Enter unit name'}
    )
    description = TextAreaField(
        'Unit Description',
        validators=[
            Length(max=1000, message='Description cannot exceed 1000 characters')
        ],
        render_kw={'placeholder': 'Describe your unit\'s mission and values (optional)', 'rows': 5}
    )
    submit = SubmitField('Create Unit (20 Gold)')

    def validate_name(self, field):
        """Check if unit name is unique."""
        existing = db.session.scalar(
            db.select(MilitaryUnit)
            .where(MilitaryUnit.name == field.data)
            .where(MilitaryUnit.is_active == True)
        )
        if existing:
            raise ValidationError('A military unit with this name already exists.')


class EditUnitForm(FlaskForm):
    """Form for editing unit description and avatar (commander only)."""
    description = TextAreaField(
        'Unit Description',
        validators=[
            Length(max=1000, message='Description cannot exceed 1000 characters')
        ],
        render_kw={'placeholder': 'Describe your unit\'s mission and values', 'rows': 5}
    )
    avatar = FileField(
        'Unit Avatar',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png'], 'Only JPG and PNG images are allowed')
        ]
    )
    submit = SubmitField('Save Changes')


class UnitApplicationForm(FlaskForm):
    """Form for applying to join a military unit."""
    submit = SubmitField('Apply to Join')


class ProcessApplicationForm(FlaskForm):
    """Form for processing a unit application."""
    action = SelectField(
        'Action',
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Process')


class PromoteMemberForm(FlaskForm):
    """Form for promoting/demoting a unit member."""
    rank = SelectField(
        'New Rank',
        choices=[
            ('officer', 'Officer'),
            ('soldier', 'Soldier'),
            ('recruit', 'Recruit')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Update Rank')


class TransferCommandForm(FlaskForm):
    """Form for transferring command to another member."""
    new_commander_id = SelectField(
        'New Commander',
        coerce=int,
        validators=[DataRequired(message='Please select a new commander')]
    )
    submit = SubmitField('Transfer Command')

    def __init__(self, members=None, *args, **kwargs):
        super(TransferCommandForm, self).__init__(*args, **kwargs)
        if members:
            self.new_commander_id.choices = [
                (m.user_id, f"{m.user.username} ({m.rank.value.title()})")
                for m in members
            ]


class DistributeItemForm(FlaskForm):
    """Form for distributing items from unit inventory to members."""
    member_id = SelectField(
        'Select Member',
        coerce=int,
        validators=[DataRequired(message='Please select a member')]
    )
    resource_id = SelectField(
        'Select Item',
        coerce=int,
        validators=[DataRequired(message='Please select an item')]
    )
    quality = SelectField(
        'Quality',
        coerce=int,
        choices=[(1, 'Q1'), (2, 'Q2'), (3, 'Q3'), (4, 'Q4'), (5, 'Q5')],
        validators=[DataRequired()]
    )
    quantity = IntegerField(
        'Quantity',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=1000, message='Quantity must be between 1 and 1000')
        ],
        render_kw={'placeholder': 'Amount to give'}
    )
    submit = SubmitField('Distribute')

    def __init__(self, members=None, inventory=None, *args, **kwargs):
        super(DistributeItemForm, self).__init__(*args, **kwargs)
        if members:
            self.member_id.choices = [
                (m.user_id, m.user.username)
                for m in members
            ]
        if inventory:
            # Get unique resources from inventory
            resources = {}
            for item in inventory:
                if item.resource_id not in resources:
                    resources[item.resource_id] = item.resource.name
            self.resource_id.choices = [(rid, name) for rid, name in resources.items()]


class UnitMessageForm(FlaskForm):
    """Form for posting a message on the unit message board."""
    content = TextAreaField(
        'Message',
        validators=[
            DataRequired(message='Message content is required'),
            Length(min=1, max=2000, message='Message must be between 1 and 2000 characters')
        ],
        render_kw={'placeholder': 'Write your message...', 'rows': 3}
    )
    submit = SubmitField('Post Message')


class CreateBountyForm(FlaskForm):
    """Form for creating a bounty contract (Minister of Defence only)."""
    battle_id = SelectField(
        'Select Battle',
        coerce=int,
        validators=[DataRequired(message='Please select a battle')]
    )
    fight_for_attacker = SelectField(
        'Fight For',
        coerce=int,
        choices=[(1, 'Attacker Side'), (0, 'Defender Side')],
        validators=[DataRequired()]
    )
    damage_required = IntegerField(
        'Damage Required',
        validators=[
            DataRequired(),
            NumberRange(min=1000, max=100000000, message='Damage must be between 1,000 and 100,000,000')
        ],
        render_kw={'placeholder': 'Minimum damage required'}
    )
    payment_amount = DecimalField(
        'Payment Amount',
        places=2,
        validators=[
            DataRequired(),
            NumberRange(min=Decimal('1'), max=Decimal('1000000'), message='Payment must be between 1 and 1,000,000')
        ],
        render_kw={'placeholder': 'Payment in local currency'}
    )
    submit = SubmitField('Create Bounty')

    def __init__(self, battles=None, *args, **kwargs):
        super(CreateBountyForm, self).__init__(*args, **kwargs)
        if battles:
            self.battle_id.choices = [
                (b.id, f"Battle #{b.id} - {b.region.name if b.region else 'Unknown'}")
                for b in battles
            ]


class ApplyForBountyForm(FlaskForm):
    """Form for applying for a bounty contract (Unit Commander only)."""
    submit = SubmitField('Apply for Contract')


class ProcessBountyApplicationForm(FlaskForm):
    """Form for approving/rejecting bounty applications (Minister of Defence only)."""
    action = SelectField(
        'Action',
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Process')


class ReviewBountyForm(FlaskForm):
    """Form for reviewing a completed bounty contract (Minister of Defence only)."""
    rating = SelectField(
        'Rating',
        coerce=int,
        choices=[
            (5, '5 Stars - Excellent'),
            (4, '4 Stars - Good'),
            (3, '3 Stars - Average'),
            (2, '2 Stars - Below Average'),
            (1, '1 Star - Poor')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Submit Review')
