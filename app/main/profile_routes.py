# app/main/profile_routes.py
# Routes related to user profiles
# Updated: trigger auto-reload

import os
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user, login_required
from sqlalchemy import func
from app.main import bp
from app.extensions import db, limiter
from app.models import User, Country, Region, country_regions
from .forms import EditProfileForm, ChooseCitizenshipForm
from datetime import datetime, timedelta
from app.utils import get_level_from_xp
from app.constants import GameConstants
from app.security import InputSanitizer

# --- Helper function for avatar processing ---
# (Moved here as it's only used by edit_profile)
def process_avatar(file_storage, user_id):
    if not file_storage: return False, None
    filename = secure_filename(file_storage.filename)
    if not filename: return False, None
    _, ext = os.path.splitext(filename)
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', GameConstants.ALLOWED_AVATAR_EXTENSIONS)
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        current_app.logger.error("UPLOAD_FOLDER not configured!")
        flash('Server configuration error for uploads.', 'danger')
        return False, None
    avatar_folder = os.path.join(upload_folder, 'avatars')
    os.makedirs(avatar_folder, exist_ok=True)
    if ext.lower()[1:] not in allowed_extensions:
         flash(f'Invalid image file type ({ext}). Allowed: {", ".join(allowed_extensions)}', 'warning')
         return False, None
    new_filename_base = str(user_id)
    avatar_filename = new_filename_base + '.png' # Standardize to PNG
    avatar_path = os.path.join(avatar_folder, avatar_filename)
    try:
        img = Image.open(file_storage.stream)
        img.verify()
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img_100x100 = ImageOps.fit(img, GameConstants.AVATAR_SIZE, Image.Resampling.LANCZOS)
        save_format = 'PNG'
        if not avatar_filename.lower().endswith('.png'):
             avatar_filename = new_filename_base + '.png'
             avatar_path = os.path.join(avatar_folder, avatar_filename)
        if img_100x100.mode != 'RGBA':
            img_100x100 = img_100x100.convert('RGBA')
        img_100x100.save(avatar_path, format=save_format)
        return True, avatar_filename
    except Exception as e:
        current_app.logger.error(f"Error processing avatar for user {user_id}: {e}", exc_info=True)
        flash('Error processing image upload. Please try a different image.', 'danger')
        return False, None


# --- Edit Profile Route ---
@bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_PROFILE_UPDATE", "10 per hour"))
def edit_profile():
    if current_user.citizenship_id is None:
         flash('Please choose your citizenship first.', 'warning')
         return redirect(url_for('main.choose_citizenship'))

    form = EditProfileForm(current_user.username) # Pass original username

    if form.validate_on_submit():
        avatar_file = form.avatar.data
        if avatar_file:
            success, filename = process_avatar(avatar_file, current_user.id)
            if success:
                current_user.avatar = True
            else:
                # Don't redirect here, let the rest of the profile save attempt
                # Flash message is handled in process_avatar
                 pass # Simply proceed without setting avatar=True

        current_user.username = form.username.data
        current_user.description = InputSanitizer.sanitize_description(form.description.data)
        try:
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('main.index')) # Redirect to dashboard after saving
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating profile for {current_user.wallet_address}: {e}", exc_info=True)
            flash('An error occurred while updating your profile. Please try again.', 'danger')

    elif request.method == 'GET':
        form.username.data = current_user.username
        form.description.data = current_user.description

    avatar_url = None
    if current_user.avatar:
         # Use timestamp query param to try and bypass cache after upload
         import time
         cache_buster = int(time.time())
         avatar_filename = f"{current_user.id}.png"
         avatar_url = url_for('static', filename=f'uploads/avatars/{avatar_filename}', _external=False, v=cache_buster)


    return render_template('edit_profile.html', title='Edit Your Profile', form=form, avatar_url=avatar_url)


# --- Public Profile View Route ---
@bp.route('/profile/<username>')
def view_profile(username):
    user = db.session.scalar(db.select(User).where(User.username == username, User.is_deleted == False))
    if user is None:
        abort(404)
    view_avatar_url = None
    if user.avatar:
        # Add cache buster here too for consistency
        import time
        cache_buster = int(time.time())
        avatar_filename = f"{user.id}.png"
        view_avatar_url = url_for('static', filename=f'uploads/avatars/{avatar_filename}', _external=False, v=cache_buster)

    # Friendship status and friends data
    friendship_status = None
    friendship_id = None
    friends_list = []

    if current_user.is_authenticated:
        if current_user.id != user.id:
            # Get friendship status with this user
            friendship_status = current_user.get_friendship_status(user.id)

            # If there's a pending request, get the friendship ID for actions
            if friendship_status in ['request_sent', 'request_received']:
                from app.models import Friendship, FriendshipStatus
                from sqlalchemy import or_
                friendship = db.session.scalar(
                    db.select(Friendship).where(
                        or_(
                            (Friendship.requester_id == current_user.id) & (Friendship.receiver_id == user.id),
                            (Friendship.requester_id == user.id) & (Friendship.receiver_id == current_user.id)
                        ),
                        Friendship.status == FriendshipStatus.PENDING
                    )
                )
                if friendship:
                    friendship_id = friendship.id

        # Get user's friends list (visible on their own profile or for all)
        friends_list = user.get_friends()

    # Check if user is online (active within last 5 minutes)
    from datetime import datetime, timedelta
    is_online = False
    if user.last_seen:
        is_online = (datetime.utcnow() - user.last_seen) < timedelta(minutes=5)

    return render_template('view_profile.html',
                           title=f"{user.username}'s Profile",
                           user=user,
                           avatar_url=view_avatar_url,
                           friendship_status=friendship_status,
                           friendship_id=friendship_id,
                           friends_list=friends_list,
                           is_online=is_online,
                           is_own_profile=(current_user.is_authenticated and current_user.id == user.id))


# --- Choose Citizenship Route ---
@bp.route('/choose-citizenship', methods=['GET', 'POST'])
@login_required
def choose_citizenship():
    if current_user.citizenship_id is not None:
        flash("You already have citizenship.", "info") # Add flash message
        return redirect(url_for('main.index'))

    form = ChooseCitizenshipForm()

    if form.validate_on_submit():
        selected_country = form.country.data
        region_id = form.region.data # This is a string ID from the select field

        # Validate that the selected region belongs to the selected country
        selected_region = db.session.scalar(
            db.select(Region).join(country_regions).where(
                country_regions.c.country_id == selected_country.id,
                Region.id == int(region_id), # Convert region_id string to int for query
                Region.is_deleted == False
            )
        )

        if not selected_region:
            flash('Invalid region selected for the chosen country.', 'danger')
            # Optionally force country/region selects to reset or retain values
            # form.region.choices = [] # Clear regions to force re-fetch via JS
        else:
            current_user.citizenship_id = selected_country.id
            current_user.current_region_id = selected_region.id # Set the validated region ID
            # Grant initial local currency based on the country selected
            initial_currency = GameConstants.INITIAL_LOCAL_CURRENCY
            current_user.add_currency(selected_country.id, initial_currency)
            try:
                db.session.commit()
                # **NAME CHANGED HERE**
                flash(f'Welcome citizen of {selected_country.name}! You start in {selected_region.name} with {initial_currency:.2f} {selected_country.currency_code}. Please set up your profile.', 'success')
                return redirect(url_for('main.edit_profile')) # Redirect to edit profile page
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error setting citizenship for {current_user.wallet_address}: {e}", exc_info=True)
                flash('An error occurred while setting your citizenship. Please try again.', 'danger')

    # For GET request or failed POST, we still pass the form to the template
    return render_template('choose_citizenship.html', title='Choose Your Citizenship', form=form)


# ==================== Session Management Routes ====================

@bp.route('/profile/sessions')
@login_required
def view_sessions():
    """View and manage active sessions."""
    from app.session_security import get_user_active_sessions, get_session_info

    # Get all active sessions for current user
    active_sessions = get_user_active_sessions(current_user.id)

    # Get current session info
    current_session_info = get_session_info()

    return render_template(
        'profile/sessions.html',
        title='Active Sessions',
        sessions=active_sessions,
        current_session=current_session_info
    )


@bp.route('/profile/sessions/terminate/<session_id>', methods=['POST'])
@login_required
def terminate_session(session_id):
    """Terminate a specific session."""
    from app.session_security import terminate_session as term_sess

    success = term_sess(current_user.id, session_id)

    if success:
        flash('Session terminated successfully.', 'success')
    else:
        flash('Could not terminate session (it may be your current session).', 'warning')

    return redirect(url_for('main.view_sessions'))


@bp.route('/profile/sessions/terminate-all', methods=['POST'])
@login_required
def terminate_all_sessions():
    """Terminate all other sessions (log out all other devices)."""
    from app.session_security import terminate_all_other_sessions

    count = terminate_all_other_sessions(current_user.id)

    if count > 0:
        flash(f'Successfully logged out {count} other session(s).', 'success')
    else:
        flash('No other active sessions found.', 'info')

    return redirect(url_for('main.view_sessions'))