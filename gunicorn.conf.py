# Gunicorn configuration file for Tactizen
# https://docs.gunicorn.org/en/stable/settings.html

import multiprocessing

# Server socket
bind = "127.0.0.1:5000"  # Only listen locally (Nginx will proxy)
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1  # Recommended formula
worker_class = "sync"  # Use "gevent" or "eventlet" for async if needed
worker_connections = 1000
timeout = 120  # Increased for long-running requests
keepalive = 5
max_requests = 1000  # Restart workers after this many requests (prevents memory leaks)
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once

# Server mechanics
daemon = False  # Let systemd manage the daemon
pidfile = "/run/tactizen/gunicorn.pid"
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# Logging
errorlog = "/var/log/tactizen/gunicorn-error.log"
accesslog = "/var/log/tactizen/gunicorn-access.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "tactizen"

# SSL (handled by Nginx, not Gunicorn)
# keyfile = None
# certfile = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Hooks for graceful shutdown
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_exit(server):
    """Called just before exiting Gunicorn."""
    pass

def worker_exit(server, worker):
    """Called when a worker exits."""
    pass
