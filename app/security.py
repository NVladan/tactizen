"""Security utilities for input validation and sanitization."""

import re
import html
import bleach
from markupsafe import Markup, escape


ALLOWED_HTML_TAGS = {
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'a', 'blockquote', 'code', 'pre',
    'img', 'div', 'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td'  # For rich text editor
}

ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'div': ['class', 'style'],
    'span': ['class', 'style'],
    'table': ['class'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    '*': ['class']
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


class InputSanitizer:
    @staticmethod
    def sanitize_html(text, allowed_tags=None, allowed_attributes=None, allowed_protocols=None):
        """
        Sanitize HTML content to prevent XSS attacks.

        Args:
            text: The HTML content to sanitize
            allowed_tags: Set of allowed HTML tags (default: ALLOWED_HTML_TAGS)
            allowed_attributes: Dict of allowed attributes per tag (default: ALLOWED_HTML_ATTRIBUTES)
            allowed_protocols: List of allowed URL protocols (default: ALLOWED_PROTOCOLS)

        Returns:
            Sanitized HTML string with dangerous content removed
        """
        if not text:
            return ''

        if allowed_tags is None:
            allowed_tags = ALLOWED_HTML_TAGS
        if allowed_attributes is None:
            allowed_attributes = ALLOWED_HTML_ATTRIBUTES
        if allowed_protocols is None:
            allowed_protocols = ALLOWED_PROTOCOLS

        cleaned = bleach.clean(
            str(text),
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )

        return bleach.linkify(cleaned, parse_email=True)

    @staticmethod
    def sanitize_username(username):
        if not username:
            return ''

        sanitized = re.sub(r'[^A-Za-z0-9 _-]', '', str(username))
        sanitized = re.sub(r'\s+', ' ', sanitized.strip())

        return sanitized

    @staticmethod
    def sanitize_description(description, max_length=500):
        """
        Sanitize plain text descriptions by escaping HTML and limiting length.
        Use this for user bios, company descriptions, party descriptions, etc.
        """
        if not description:
            return ''

        sanitized = bleach.clean(str(description), tags=set(), strip=True)

        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        sanitized = re.sub(r'\s+', ' ', sanitized.strip())

        return sanitized

    @staticmethod
    def sanitize_integer(value, min_val=None, max_val=None):
        try:
            int_value = int(value)

            if min_val is not None and int_value < min_val:
                raise ValueError(f"Value {int_value} is below minimum {min_val}")

            if max_val is not None and int_value > max_val:
                raise ValueError(f"Value {int_value} exceeds maximum {max_val}")

            return int_value

        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid integer value: {value}") from e

    @staticmethod
    def sanitize_slug(text):
        if not text:
            return ''

        slug = str(text).lower()
        slug = re.sub(r'[^a-z0-9-]', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')

        return slug

    @staticmethod
    def is_safe_redirect_url(url):
        """Prevents open redirect vulnerabilities."""
        if not url:
            return False

        if url.startswith('/') and not url.startswith('//'):
            return True

        return False

    @staticmethod
    def sanitize_decimal(value, min_val=None, max_val=None, max_decimal_places=2):
        """
        Sanitize and validate decimal/float values.

        Args:
            value: The value to sanitize (string, int, float, or Decimal)
            min_val: Minimum allowed value (optional)
            max_val: Maximum allowed value (optional)
            max_decimal_places: Maximum decimal places allowed (default: 2)

        Returns:
            Decimal object

        Raises:
            ValueError: If value is invalid or out of range
        """
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

        try:
            # Convert to Decimal
            decimal_value = Decimal(str(value))

            # Check if it's a valid number (not NaN or Infinity)
            if not decimal_value.is_finite():
                raise ValueError(f"Invalid decimal value: {value}")

            # Check minimum value
            if min_val is not None and decimal_value < Decimal(str(min_val)):
                raise ValueError(f"Value {decimal_value} is below minimum {min_val}")

            # Check maximum value
            if max_val is not None and decimal_value > Decimal(str(max_val)):
                raise ValueError(f"Value {decimal_value} exceeds maximum {max_val}")

            # Quantize to max decimal places
            if max_decimal_places is not None:
                quantize_value = Decimal('0.1') ** max_decimal_places
                decimal_value = decimal_value.quantize(quantize_value, rounding=ROUND_HALF_UP)

            return decimal_value

        except (TypeError, ValueError, InvalidOperation) as e:
            raise ValueError(f"Invalid decimal value: {value}") from e

    @staticmethod
    def sanitize_positive_integer(value, max_val=None):
        """
        Sanitize and validate positive integers (quantity, ID, etc).

        Args:
            value: The value to sanitize
            max_val: Maximum allowed value (optional)

        Returns:
            Positive integer

        Raises:
            ValueError: If value is not a positive integer or out of range
        """
        try:
            int_value = int(value)

            if int_value < 1:
                raise ValueError(f"Value must be positive, got {int_value}")

            if max_val is not None and int_value > max_val:
                raise ValueError(f"Value {int_value} exceeds maximum {max_val}")

            return int_value

        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid positive integer: {value}") from e

    @staticmethod
    def sanitize_quality(value):
        """
        Sanitize and validate quality values (1-5).

        Args:
            value: The quality value to sanitize

        Returns:
            Integer between 1 and 5

        Raises:
            ValueError: If value is not a valid quality level
        """
        try:
            quality = int(value)

            if quality < 1 or quality > 5:
                raise ValueError(f"Quality must be between 1 and 5, got {quality}")

            return quality

        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid quality value: {value}") from e

    @staticmethod
    def sanitize_boolean(value):
        """
        Sanitize and validate boolean values.

        Args:
            value: The value to sanitize (can be bool, string, int)

        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ('true', '1', 'yes', 'on'):
                return True
            elif value_lower in ('false', '0', 'no', 'off', ''):
                return False

        if isinstance(value, int):
            return bool(value)

        raise ValueError(f"Invalid boolean value: {value}")

    @staticmethod
    def sanitize_enum_choice(value, allowed_choices, case_sensitive=False):
        """
        Sanitize and validate enum/choice values.

        Args:
            value: The value to check
            allowed_choices: List or set of allowed values
            case_sensitive: Whether to enforce case sensitivity (default: False)

        Returns:
            The validated value

        Raises:
            ValueError: If value is not in allowed choices
        """
        if not value:
            raise ValueError("Value is required")

        value_str = str(value)

        if not case_sensitive:
            value_str = value_str.lower()
            allowed_choices = [str(choice).lower() for choice in allowed_choices]

        if value_str not in allowed_choices:
            raise ValueError(f"Invalid choice: {value}. Allowed: {', '.join(map(str, allowed_choices))}")

        return value_str

    @staticmethod
    def sanitize_wallet_address(address):
        """
        Sanitize and validate Ethereum wallet address.

        Args:
            address: The wallet address to validate

        Returns:
            Lowercased wallet address

        Raises:
            ValueError: If address is invalid
        """
        if not address:
            raise ValueError("Wallet address is required")

        # Basic Ethereum address format check (0x + 40 hex characters)
        address_str = str(address).strip()

        if not re.match(r'^0x[a-fA-F0-9]{40}$', address_str):
            raise ValueError(f"Invalid Ethereum wallet address format: {address}")

        return address_str.lower()

    @staticmethod
    def sanitize_resource_id(resource_id):
        """
        Sanitize and validate resource ID.

        Args:
            resource_id: The resource ID to validate

        Returns:
            Integer resource ID

        Raises:
            ValueError: If resource_id is invalid
        """
        return InputSanitizer.sanitize_positive_integer(resource_id, max_val=10000)

    @staticmethod
    def sanitize_country_id(country_id):
        """
        Sanitize and validate country ID.

        Args:
            country_id: The country ID to validate

        Returns:
            Integer country ID

        Raises:
            ValueError: If country_id is invalid
        """
        return InputSanitizer.sanitize_positive_integer(country_id, max_val=1000)


class SQLInjectionPrevention:
    DANGEROUS_SQL_PATTERNS = [
        r'(\bunion\b|\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b|\bcreate\b)',
        r'(--|;|\/\*|\*\/)',
        r'(\bor\b.*=.*\bor\b)',
        r'(\'.*--)',
    ]

    @classmethod
    def contains_sql_injection(cls, text):
        if not text:
            return False

        text_lower = str(text).lower()

        for pattern in cls.DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True

        return False

    @classmethod
    def sanitize_for_like(cls, text):
        if not text:
            return ''

        text = str(text).replace('\\', '\\\\')
        text = text.replace('%', '\\%')
        text = text.replace('_', '\\_')

        return text


def add_security_headers(response):
    """Add security headers including CSP to all responses."""
    from flask import current_app

    headers = current_app.config.get('SECURITY_HEADERS', {})
    for header, value in headers.items():
        response.headers[header] = value

    csp_config = current_app.config.get('CONTENT_SECURITY_POLICY', {})
    if csp_config:
        csp_header = build_csp_header(csp_config)
        response.headers['Content-Security-Policy'] = csp_header

    return response


def build_csp_header(csp_config):
    """Build CSP header string from config dictionary."""
    directives = []

    for directive, sources in csp_config.items():
        if not sources:
            directives.append(directive)
        else:
            sources_str = ' '.join(sources)
            directives.append(f"{directive} {sources_str}")

    return '; '.join(directives)


def safe_username(username):
    if not username:
        return ''
    return escape(username)


def safe_description(description):
    if not description:
        return ''

    escaped = escape(description)
    with_breaks = escaped.replace('\n', Markup('<br>'))

    return Markup(with_breaks)


def register_security_filters(app):
    app.jinja_env.filters['safe_username'] = safe_username
    app.jinja_env.filters['safe_description'] = safe_description


# ==================== Request Validation Decorators ====================

from functools import wraps
from flask import request, jsonify, flash, redirect, url_for


def validate_request_data(schema):
    """
    Decorator to validate request data (form or JSON) against a schema.

    Schema format:
    {
        'field_name': {
            'type': 'integer'|'decimal'|'string'|'boolean'|'enum',
            'required': True|False,
            'min': value (for numbers),
            'max': value (for numbers),
            'choices': [list] (for enum),
            'sanitizer': callable (custom sanitizer function)
        }
    }

    Example:
    @validate_request_data({
        'quantity': {'type': 'integer', 'required': True, 'min': 1, 'max': 1000},
        'quality': {'type': 'integer', 'required': False, 'min': 1, 'max': 5}
    })
    def my_route():
        # Access validated data via request.validated_data
        quantity = request.validated_data['quantity']
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get data from request (form data or JSON)
            if request.is_json:
                data = request.get_json() or {}
            else:
                data = request.form.to_dict()

            validated_data = {}
            errors = []

            for field_name, rules in schema.items():
                value = data.get(field_name)
                field_type = rules.get('type', 'string')
                required = rules.get('required', False)

                # Check if required field is missing
                if required and (value is None or value == ''):
                    errors.append(f"{field_name} is required")
                    continue

                # Skip validation if field is optional and not provided
                if value is None or value == '':
                    validated_data[field_name] = None
                    continue

                # Validate based on type
                try:
                    if field_type == 'integer':
                        validated_data[field_name] = InputSanitizer.sanitize_integer(
                            value,
                            min_val=rules.get('min'),
                            max_val=rules.get('max')
                        )
                    elif field_type == 'positive_integer':
                        validated_data[field_name] = InputSanitizer.sanitize_positive_integer(
                            value,
                            max_val=rules.get('max')
                        )
                    elif field_type == 'decimal':
                        validated_data[field_name] = InputSanitizer.sanitize_decimal(
                            value,
                            min_val=rules.get('min'),
                            max_val=rules.get('max'),
                            max_decimal_places=rules.get('decimal_places', 2)
                        )
                    elif field_type == 'boolean':
                        validated_data[field_name] = InputSanitizer.sanitize_boolean(value)
                    elif field_type == 'enum':
                        validated_data[field_name] = InputSanitizer.sanitize_enum_choice(
                            value,
                            rules.get('choices', [])
                        )
                    elif field_type == 'quality':
                        validated_data[field_name] = InputSanitizer.sanitize_quality(value)
                    elif field_type == 'string':
                        # Use custom sanitizer if provided, otherwise basic string sanitization
                        if 'sanitizer' in rules:
                            validated_data[field_name] = rules['sanitizer'](value)
                        else:
                            validated_data[field_name] = str(value).strip()

                            # Check max length if specified
                            max_length = rules.get('max_length')
                            if max_length and len(validated_data[field_name]) > max_length:
                                errors.append(f"{field_name} exceeds maximum length of {max_length}")
                    else:
                        validated_data[field_name] = value

                except ValueError as e:
                    errors.append(f"{field_name}: {str(e)}")

            # If there are validation errors, return error response
            if errors:
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': '; '.join(errors)}), 400
                else:
                    for error in errors:
                        flash(error, 'error')
                    return redirect(request.referrer or url_for('main.index'))

            # Store validated data on request object
            request.validated_data = validated_data

            return f(*args, **kwargs)

        return decorated_function
    return decorator
