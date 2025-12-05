# app/main/newspaper_routes.py
"""Routes for the newspaper system."""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, and_, or_
from app.main import bp
from app.extensions import db
from app.models import (
    Newspaper, Article, ArticleVote, NewspaperSubscription, ArticleComment, Country
)
from app.main.newspaper_forms import (
    CreateNewspaperForm, EditNewspaperForm, WriteArticleForm,
    EditArticleForm, CommentForm
)
from app.exceptions import InsufficientFundsError
from app.models.currency import log_transaction
from app.security import InputSanitizer
import logging

logger = logging.getLogger(__name__)


# --- Helper Functions ---
def save_avatar(avatar_file, folder_name, item_id):
    """
    Save an avatar file for a newspaper.

    Args:
        avatar_file: The file from the form
        folder_name: Either 'newspapers' for newspaper avatars
        item_id: The ID of the newspaper

    Returns:
        True if successful, False otherwise
    """
    if not avatar_file:
        return False

    try:
        # Get file extension
        filename = secure_filename(avatar_file.filename)
        file_ext = os.path.splitext(filename)[1].lower()

        # Create folder path
        folder_path = os.path.join(current_app.root_path, 'static', 'avatars', folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Save with ID-based filename
        avatar_filename = f"{item_id}{file_ext}"
        save_path = os.path.join(folder_path, avatar_filename)

        # Save file
        avatar_file.save(save_path)
        return True
    except Exception as e:
        logger.error(f"Error saving {folder_name} avatar: {e}")
        return False


# --- Newspaper Routes ---
@bp.route('/community/newspaper')
@login_required
def my_newspaper():
    """View or redirect to create newspaper if user doesn't have one."""
    # Check if user has a newspaper
    newspaper = db.session.scalar(
        db.select(Newspaper).where(
            Newspaper.owner_id == current_user.id,
            Newspaper.is_deleted == False
        )
    )

    if newspaper:
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper.id))
    else:
        return redirect(url_for('main.create_newspaper'))


@bp.route('/community/newspaper/create', methods=['GET', 'POST'])
@login_required
def create_newspaper():
    """Create a new newspaper (costs 5 Gold)."""
    # Check if user already has a newspaper
    existing = db.session.scalar(
        db.select(Newspaper).where(
            Newspaper.owner_id == current_user.id,
            Newspaper.is_deleted == False
        )
    )
    if existing:
        flash('You already own a newspaper.', 'warning')
        return redirect(url_for('main.view_newspaper', newspaper_id=existing.id))

    # Check if user has citizenship
    if not current_user.citizenship_id:
        flash('You must have citizenship to create a newspaper.', 'danger')
        return redirect(url_for('main.index'))

    form = CreateNewspaperForm()

    if form.validate_on_submit():
        try:
            # Deduct 5 Gold with row-level locking
            from app.services.currency_service import CurrencyService
            success, message, _ = CurrencyService.deduct_gold(
                current_user.id, Decimal('5.0'), 'Newspaper creation'
            )
            if not success:
                flash(f'Could not deduct gold: {message}', 'danger')
                return redirect(url_for('main.my_newspaper'))

            # Create newspaper
            newspaper = Newspaper(
                name=form.name.data,
                description=InputSanitizer.sanitize_description(form.description.data),
                owner_id=current_user.id,
                country_id=current_user.citizenship_id,
                avatar=False
            )
            db.session.add(newspaper)
            db.session.flush()  # Get the newspaper ID

            # Save avatar if provided
            if form.avatar.data:
                if save_avatar(form.avatar.data, 'newspapers', newspaper.id):
                    newspaper.avatar = True

            # Log transaction
            log_transaction(
                user=current_user,
                transaction_type='newspaper_creation',
                amount=Decimal('5.0'),
                currency_type='gold',
                balance_after=current_user.gold,  # Balance after deduction
                country_id=current_user.citizenship_id,
                description=f"Created newspaper: {newspaper.name}"
            )

            db.session.commit()
            flash(f'Newspaper "{newspaper.name}" created successfully!', 'success')
            return redirect(url_for('main.view_newspaper', newspaper_id=newspaper.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating newspaper: {e}")
            flash('An error occurred while creating the newspaper.', 'danger')
            return redirect(url_for('main.my_newspaper'))

    return render_template('newspaper/create_newspaper.html',
                         title='Create Newspaper',
                         form=form)


@bp.route('/community/newspaper/<int:newspaper_id>')
@login_required
def view_newspaper(newspaper_id):
    """View a specific newspaper and its articles."""
    newspaper = db.session.get(Newspaper, newspaper_id)

    if not newspaper or newspaper.is_deleted:
        abort(404)

    # Get articles (non-deleted, ordered by creation date)
    articles = db.session.scalars(
        db.select(Article)
        .where(Article.newspaper_id == newspaper_id)
        .where(Article.is_deleted == False)
        .order_by(Article.created_at.desc())
    ).all()

    # Check if current user is subscribed
    is_subscribed = False
    if current_user.is_authenticated:
        subscription = db.session.scalar(
            db.select(NewspaperSubscription).where(
                NewspaperSubscription.newspaper_id == newspaper_id,
                NewspaperSubscription.subscriber_id == current_user.id
            )
        )
        is_subscribed = subscription is not None

    return render_template('newspaper/view_newspaper.html',
                         title=newspaper.name,
                         newspaper=newspaper,
                         articles=articles,
                         is_subscribed=is_subscribed)


@bp.route('/community/newspaper/<int:newspaper_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_newspaper(newspaper_id):
    """Edit newspaper details (owner only)."""
    newspaper = db.session.get(Newspaper, newspaper_id)

    if not newspaper or newspaper.is_deleted:
        abort(404)

    # Check ownership
    if newspaper.owner_id != current_user.id:
        flash('You do not have permission to edit this newspaper.', 'danger')
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))

    form = EditNewspaperForm(
        original_name=newspaper.name,
        country_id=newspaper.country_id,
        newspaper_id=newspaper.id
    )

    if form.validate_on_submit():
        try:
            newspaper.name = form.name.data
            newspaper.description = InputSanitizer.sanitize_description(form.description.data)

            # Save avatar if provided
            if form.avatar.data:
                if save_avatar(form.avatar.data, 'newspapers', newspaper.id):
                    newspaper.avatar = True

            db.session.commit()
            flash('Newspaper updated successfully!', 'success')
            return redirect(url_for('main.view_newspaper', newspaper_id=newspaper.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating newspaper: {e}")
            flash('An error occurred while updating the newspaper.', 'danger')

    elif request.method == 'GET':
        form.name.data = newspaper.name
        form.description.data = newspaper.description

    return render_template('newspaper/edit_newspaper.html',
                         title='Edit Newspaper',
                         form=form,
                         newspaper=newspaper)


@bp.route('/community/newspaper/<int:newspaper_id>/delete', methods=['POST'])
@login_required
def delete_newspaper(newspaper_id):
    """Soft delete a newspaper (owner only)."""
    newspaper = db.session.get(Newspaper, newspaper_id)

    if not newspaper or newspaper.is_deleted:
        abort(404)

    # Check ownership
    if newspaper.owner_id != current_user.id:
        flash('You do not have permission to delete this newspaper.', 'danger')
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))

    try:
        newspaper.soft_delete()
        db.session.commit()
        flash('Newspaper deleted successfully.', 'success')
        return redirect(url_for('main.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting newspaper: {e}")
        flash('An error occurred while deleting the newspaper.', 'danger')
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))


# --- Article Routes ---
@bp.route('/community/newspaper/<int:newspaper_id>/article/new', methods=['GET', 'POST'])
@login_required
def write_article(newspaper_id):
    """Write a new article for the newspaper (owner only)."""
    newspaper = db.session.get(Newspaper, newspaper_id)

    if not newspaper or newspaper.is_deleted:
        abort(404)

    # Check ownership
    if newspaper.owner_id != current_user.id:
        flash('Only the newspaper owner can write articles.', 'danger')
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))

    form = WriteArticleForm()

    if form.validate_on_submit():
        try:
            article = Article(
                title=form.title.data,
                content=InputSanitizer.sanitize_html(form.content.data),
                newspaper_id=newspaper_id,
                author_id=current_user.id
            )
            db.session.add(article)
            db.session.commit()
            flash('Article published successfully!', 'success')
            return redirect(url_for('main.view_article',
                                  newspaper_id=newspaper_id,
                                  article_id=article.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error publishing article: {e}")
            flash('An error occurred while publishing the article.', 'danger')

    return render_template('newspaper/write_article.html',
                         title='Write Article',
                         form=form,
                         newspaper=newspaper)


@bp.route('/community/newspaper/<int:newspaper_id>/article/<int:article_id>')
@login_required
def view_article(newspaper_id, article_id):
    """View a specific article with comments."""
    article = db.session.get(Article, article_id)

    if not article or article.is_deleted or article.newspaper_id != newspaper_id:
        abort(404)

    # Get top-level comments (not deleted, no parent)
    comments = db.session.scalars(
        db.select(ArticleComment)
        .where(ArticleComment.article_id == article_id)
        .where(ArticleComment.is_deleted == False)
        .where(ArticleComment.parent_comment_id == None)
        .order_by(ArticleComment.created_at.asc())
    ).all()

    # Check if user has voted
    has_voted = False
    if current_user.is_authenticated:
        has_voted = article.has_user_voted(current_user.id)

    # Check if current user is subscribed to this newspaper
    is_subscribed = False
    if current_user.is_authenticated:
        subscription = db.session.scalar(
            db.select(NewspaperSubscription).where(
                NewspaperSubscription.newspaper_id == newspaper_id,
                NewspaperSubscription.subscriber_id == current_user.id
            )
        )
        is_subscribed = subscription is not None

    comment_form = CommentForm()

    return render_template('newspaper/view_article.html',
                         title=article.title,
                         article=article,
                         comments=comments,
                         has_voted=has_voted,
                         is_subscribed=is_subscribed,
                         comment_form=comment_form)


@bp.route('/community/newspaper/<int:newspaper_id>/article/<int:article_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_article(newspaper_id, article_id):
    """Edit an article (owner only)."""
    article = db.session.get(Article, article_id)

    if not article or article.is_deleted or article.newspaper_id != newspaper_id:
        abort(404)

    # Check if user is the newspaper owner
    if article.newspaper.owner_id != current_user.id:
        flash('You do not have permission to edit this article.', 'danger')
        return redirect(url_for('main.view_article',
                              newspaper_id=newspaper_id,
                              article_id=article_id))

    form = EditArticleForm()

    if form.validate_on_submit():
        try:
            article.title = form.title.data
            article.content = InputSanitizer.sanitize_html(form.content.data)
            db.session.commit()
            flash('Article updated successfully!', 'success')
            return redirect(url_for('main.view_article',
                                  newspaper_id=newspaper_id,
                                  article_id=article_id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating article: {e}")
            flash('An error occurred while updating the article.', 'danger')

    elif request.method == 'GET':
        form.title.data = article.title
        form.content.data = article.content

    return render_template('newspaper/edit_article.html',
                         title='Edit Article',
                         form=form,
                         article=article,
                         newspaper_id=newspaper_id)


@bp.route('/community/newspaper/<int:newspaper_id>/article/<int:article_id>/delete', methods=['POST'])
@login_required
def delete_article(newspaper_id, article_id):
    """Soft delete an article (owner only)."""
    article = db.session.get(Article, article_id)

    if not article or article.is_deleted or article.newspaper_id != newspaper_id:
        abort(404)

    # Check ownership
    if article.newspaper.owner_id != current_user.id:
        flash('You do not have permission to delete this article.', 'danger')
        return redirect(url_for('main.view_article',
                              newspaper_id=newspaper_id,
                              article_id=article_id))

    try:
        article.soft_delete()
        db.session.commit()
        flash('Article deleted successfully.', 'success')
        return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting article: {e}")
        flash('An error occurred while deleting the article.', 'danger')
        return redirect(url_for('main.view_article',
                              newspaper_id=newspaper_id,
                              article_id=article_id))


# --- Voting Routes ---
@bp.route('/community/article/<int:article_id>/vote', methods=['POST'])
@login_required
def vote_article(article_id):
    """Vote (upvote) on an article."""
    article = db.session.get(Article, article_id)

    if not article or article.is_deleted:
        abort(404)

    # Check if user has already voted
    existing_vote = db.session.scalar(
        db.select(ArticleVote).where(
            ArticleVote.article_id == article_id,
            ArticleVote.user_id == current_user.id
        )
    )

    if existing_vote:
        flash('You have already voted on this article.', 'warning')
    else:
        try:
            vote = ArticleVote(
                article_id=article_id,
                user_id=current_user.id
            )
            db.session.add(vote)
            db.session.commit()
            flash('Vote added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error voting on article: {e}")
            flash('An error occurred while voting.', 'danger')

    return redirect(url_for('main.view_article',
                          newspaper_id=article.newspaper_id,
                          article_id=article_id))


# --- Subscription Routes ---
@bp.route('/community/newspaper/<int:newspaper_id>/subscribe', methods=['POST'])
@login_required
def subscribe_newspaper(newspaper_id):
    """Subscribe to a newspaper."""
    newspaper = db.session.get(Newspaper, newspaper_id)

    if not newspaper or newspaper.is_deleted:
        abort(404)

    # Check if already subscribed
    existing = db.session.scalar(
        db.select(NewspaperSubscription).where(
            NewspaperSubscription.newspaper_id == newspaper_id,
            NewspaperSubscription.subscriber_id == current_user.id
        )
    )

    if existing:
        flash('You are already subscribed to this newspaper.', 'warning')
    else:
        try:
            subscription = NewspaperSubscription(
                newspaper_id=newspaper_id,
                subscriber_id=current_user.id
            )
            db.session.add(subscription)
            db.session.commit()
            flash(f'Subscribed to "{newspaper.name}" successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error subscribing to newspaper: {e}")
            flash('An error occurred while subscribing.', 'danger')

    return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))


@bp.route('/community/newspaper/<int:newspaper_id>/unsubscribe', methods=['POST'])
@login_required
def unsubscribe_newspaper(newspaper_id):
    """Unsubscribe from a newspaper."""
    subscription = db.session.scalar(
        db.select(NewspaperSubscription).where(
            NewspaperSubscription.newspaper_id == newspaper_id,
            NewspaperSubscription.subscriber_id == current_user.id
        )
    )

    if not subscription:
        flash('You are not subscribed to this newspaper.', 'warning')
    else:
        try:
            db.session.delete(subscription)
            db.session.commit()
            flash('Unsubscribed successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error unsubscribing from newspaper: {e}")
            flash('An error occurred while unsubscribing.', 'danger')

    return redirect(url_for('main.view_newspaper', newspaper_id=newspaper_id))


# --- Comment Routes ---
@bp.route('/community/article/<int:article_id>/comment', methods=['POST'])
@login_required
def post_comment(article_id):
    """Post a comment on an article."""
    article = db.session.get(Article, article_id)

    if not article or article.is_deleted:
        abort(404)

    form = CommentForm()

    if form.validate_on_submit():
        try:
            # Check parent comment nesting level if replying
            parent_id = form.parent_comment_id.data if form.parent_comment_id.data else None

            if parent_id:
                parent_comment = db.session.get(ArticleComment, int(parent_id))
                if parent_comment and not parent_comment.can_reply:
                    flash('Maximum comment nesting level reached.', 'warning')
                    return redirect(url_for('main.view_article',
                                          newspaper_id=article.newspaper_id,
                                          article_id=article_id))

            comment = ArticleComment(
                content=form.content.data,
                article_id=article_id,
                user_id=current_user.id,
                parent_comment_id=int(parent_id) if parent_id else None
            )
            db.session.add(comment)
            db.session.commit()
            flash('Comment posted successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error posting comment: {e}")
            flash('An error occurred while posting your comment.', 'danger')

    return redirect(url_for('main.view_article',
                          newspaper_id=article.newspaper_id,
                          article_id=article_id))
