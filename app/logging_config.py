"""Logging configuration for Tactizen application."""

import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


class LogConfig:
    LOG_DIR = 'logs'

    APP_LOG_FILE = 'app.log'
    ERROR_LOG_FILE = 'error.log'
    TRANSACTION_LOG_FILE = 'transactions.log'
    SECURITY_LOG_FILE = 'security.log'

    LOG_LEVELS = {
        'development': logging.DEBUG,
        'testing': logging.INFO,
        'production': logging.INFO,
    }

    MAX_BYTES = 10 * 1024 * 1024
    BACKUP_COUNT = 10

    DETAILED_FORMAT = (
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
    )
    SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    TRANSACTION_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

    @classmethod
    def get_log_level(cls, env='development'):
        return cls.LOG_LEVELS.get(env, logging.INFO)


def setup_logging(app):
    env = app.config.get('ENV', 'development')
    log_level = LogConfig.get_log_level(env)

    log_dir = os.path.join(app.root_path, '..', LogConfig.LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)

    app.logger.handlers.clear()
    app.logger.setLevel(log_level)

    if env == 'development':
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(LogConfig.SIMPLE_FORMAT)
        console_handler.setFormatter(console_formatter)
        app.logger.addHandler(console_handler)

    app_log_path = os.path.join(log_dir, LogConfig.APP_LOG_FILE)
    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=LogConfig.MAX_BYTES,
        backupCount=LogConfig.BACKUP_COUNT
    )
    app_handler.setLevel(log_level)
    app_formatter = logging.Formatter(LogConfig.DETAILED_FORMAT)
    app_handler.setFormatter(app_formatter)
    app.logger.addHandler(app_handler)

    error_log_path = os.path.join(log_dir, LogConfig.ERROR_LOG_FILE)
    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=LogConfig.MAX_BYTES,
        backupCount=LogConfig.BACKUP_COUNT
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(LogConfig.DETAILED_FORMAT)
    error_handler.setFormatter(error_formatter)
    app.logger.addHandler(error_handler)

    transaction_log_path = os.path.join(log_dir, LogConfig.TRANSACTION_LOG_FILE)
    transaction_handler = TimedRotatingFileHandler(
        transaction_log_path,
        when='midnight',
        interval=1,
        backupCount=90
    )
    transaction_handler.setLevel(logging.INFO)
    transaction_formatter = logging.Formatter(LogConfig.TRANSACTION_FORMAT)
    transaction_handler.setFormatter(transaction_formatter)

    transaction_logger = logging.getLogger('transactions')
    transaction_logger.setLevel(logging.INFO)
    transaction_logger.handlers.clear()
    transaction_logger.addHandler(transaction_handler)
    transaction_logger.propagate = False

    security_log_path = os.path.join(log_dir, LogConfig.SECURITY_LOG_FILE)
    security_handler = TimedRotatingFileHandler(
        security_log_path,
        when='midnight',
        interval=1,
        backupCount=365
    )
    security_handler.setLevel(logging.WARNING)
    security_formatter = logging.Formatter(LogConfig.DETAILED_FORMAT)
    security_handler.setFormatter(security_formatter)

    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.WARNING)
    security_logger.handlers.clear()
    security_logger.addHandler(security_handler)
    security_logger.propagate = False

    app.logger.info(f'=' * 80)
    app.logger.info(f'Tactizen Application Starting')
    app.logger.info(f'Environment: {env}')
    app.logger.info(f'Log Level: {logging.getLevelName(log_level)}')
    app.logger.info(f'Log Directory: {log_dir}')
    app.logger.info(f'=' * 80)


def get_transaction_logger():
    return logging.getLogger('transactions')


def get_security_logger():
    return logging.getLogger('security')


def log_transaction(user_id, transaction_type, amount, currency, description='', **kwargs):
    logger = get_transaction_logger()

    metadata = ' | '.join([f'{k}={v}' for k, v in kwargs.items()])
    log_message = (
        f"USER:{user_id} | TYPE:{transaction_type} | "
        f"AMOUNT:{amount} | CURRENCY:{currency} | "
        f"DESC:{description}"
    )
    if metadata:
        log_message += f" | {metadata}"

    logger.info(log_message)


def log_security_event(event_type, user_id=None, ip_address=None, description='', severity='WARNING'):
    logger = get_security_logger()

    log_message = f"EVENT:{event_type}"
    if user_id:
        log_message += f" | USER:{user_id}"
    if ip_address:
        log_message += f" | IP:{ip_address}"
    if description:
        log_message += f" | DESC:{description}"

    log_func = getattr(logger, severity.lower(), logger.warning)
    log_func(log_message)


def log_api_call(endpoint, method, user_id=None, status_code=None, duration_ms=None):
    logger = logging.getLogger(__name__)

    log_message = f"API | {method} {endpoint}"
    if user_id:
        log_message += f" | USER:{user_id}"
    if status_code:
        log_message += f" | STATUS:{status_code}"
    if duration_ms:
        log_message += f" | DURATION:{duration_ms}ms"

    logger.info(log_message)


def log_error_with_context(error, context=None):
    logger = logging.getLogger(__name__)

    log_message = f"ERROR: {str(error)}"
    if context:
        context_str = ' | '.join([f'{k}={v}' for k, v in context.items()])
        log_message += f" | CONTEXT: {context_str}"

    logger.error(log_message, exc_info=True)
