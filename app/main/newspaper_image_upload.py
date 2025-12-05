# app/main/newspaper_image_upload.py
"""Image upload handler for newspaper articles."""

import os
import uuid
import io
from flask import jsonify, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from PIL import Image
from app.main import bp
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB (before compression)
MAX_IMAGE_WIDTH = 1200  # Maximum width in pixels
MAX_IMAGE_HEIGHT = 1200  # Maximum height in pixels
JPEG_QUALITY = 85  # JPEG compression quality (0-100)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def resize_and_compress_image(image_file, max_width=MAX_IMAGE_WIDTH, max_height=MAX_IMAGE_HEIGHT):
    """
    Resize and compress an image to reduce file size.

    Args:
        image_file: File object containing the image
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels

    Returns:
        tuple: (compressed_image_bytes, file_extension)
    """
    try:
        # Open image
        img = Image.open(image_file)

        # Convert RGBA to RGB if necessary (for JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Get original dimensions
        original_width, original_height = img.size

        # Calculate new dimensions maintaining aspect ratio
        if original_width > max_width or original_height > max_height:
            # Calculate scaling factor
            width_ratio = max_width / original_width
            height_ratio = max_height / original_height
            scale_ratio = min(width_ratio, height_ratio)

            new_width = int(original_width * scale_ratio)
            new_height = int(original_height * scale_ratio)

            # Resize image with high-quality resampling
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {original_width}x{original_height} to {new_width}x{new_height}")

        # Save to bytes buffer with compression
        output = io.BytesIO()

        # Always save as JPEG for better compression (unless it's GIF)
        if image_file.filename and image_file.filename.lower().endswith('.gif'):
            img.save(output, format='GIF', optimize=True)
            file_ext = '.gif'
        else:
            img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            file_ext = '.jpg'

        output.seek(0)
        compressed_bytes = output.getvalue()

        logger.info(f"Compressed image to {len(compressed_bytes) / 1024:.2f} KB")

        return compressed_bytes, file_ext

    except Exception as e:
        logger.error(f"Error resizing/compressing image: {e}")
        raise


@bp.route('/newspaper/upload-image', methods=['POST'])
@login_required
def upload_article_image():
    """Upload image for article content with automatic resizing and compression."""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        # Check if file is selected
        if file.filename == '':
            # Handle pasted images that might not have a filename
            file.filename = 'pasted_image.png'

        # Check file extension (or set default for pasted images)
        if not allowed_file(file.filename):
            # If no valid extension, assume it's a pasted image
            file.filename = 'pasted_image.png'

        # Get original file size for logging
        file.seek(0, os.SEEK_END)
        original_size = file.tell()
        file.seek(0)

        logger.info(f"Receiving image upload: {file.filename}, original size: {original_size / 1024:.2f} KB")

        # Only enforce size limit BEFORE compression
        if original_size > MAX_IMAGE_SIZE:
            # Still try to compress it, but warn if it's extremely large
            if original_size > MAX_IMAGE_SIZE * 3:  # More than 15MB
                return jsonify({
                    'success': False,
                    'error': f'Image too large ({original_size // (1024*1024)}MB). Maximum is {MAX_IMAGE_SIZE // (1024*1024)}MB.'
                }), 400

        # Resize and compress the image
        try:
            compressed_bytes, file_ext = resize_and_compress_image(file)
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return jsonify({
                'success': False,
                'error': 'Could not process image. Please try a different image.'
            }), 400

        # Generate unique filename with correct extension
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"

        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'article_images')
        os.makedirs(upload_dir, exist_ok=True)

        # Save compressed image
        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(compressed_bytes)

        # Return URL
        image_url = f"/static/uploads/article_images/{unique_filename}"

        compressed_size = len(compressed_bytes)
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        logger.info(f"User {current_user.id} uploaded article image: {unique_filename}, "
                   f"compressed from {original_size / 1024:.2f} KB to {compressed_size / 1024:.2f} KB "
                   f"({compression_ratio:.1f}% reduction)")

        return jsonify({
            'success': True,
            'url': image_url
        }), 200

    except Exception as e:
        logger.error(f"Error uploading article image: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Server error while uploading image'
        }), 500
