# Server Optimization Roadmap

## Target Hardware
- **CPU**: Intel Xeon E5-1650v4 - 6 cores / 12 threads - 3.6GHz/4GHz
- **RAM**: 64GB DDR4 2133MHz
- **Storage**: 2× 450GB SSD NVMe Soft RAID
- **OS**: Ubuntu 25
- **Database**: MySQL (same server)
- **Expected Load**: ~1000 concurrent users max
- **Peak Hours**: 21:00 CET

---

## 1. Gunicorn Configuration
**What it does**: Gunicorn spawns multiple worker processes to handle requests in parallel.

**Recommended config** (`gunicorn.conf.py`):
```python
workers = 9  # (2 × CPU cores) + 1 = optimal for mixed I/O workloads
worker_class = 'gevent'  # Async workers for handling many connections
threads = 4  # Threads per worker
worker_connections = 1000  # Max simultaneous connections per worker
max_requests = 5000  # Recycle workers after X requests (prevents memory leaks)
max_requests_jitter = 500  # Random jitter to prevent all workers restarting at once
timeout = 30  # Kill workers that hang
keepalive = 5  # Keep connections open for 5 seconds
```

**Expected improvement**: Handle 1000+ concurrent users with low latency

---

## 2. Nginx Reverse Proxy
**What it does**: Nginx handles static files, SSL, load balancing, and connection buffering.

**Recommended config**:
```nginx
worker_processes auto;  # Match CPU cores
worker_connections 4096;

upstream flask_app {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # Static files served by Nginx (not Flask)
    location /static/ {
        alias /path/to/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://flask_app;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**Expected improvement**: 10-50x faster static file serving, reduced Flask load

---

## 3. Redis Caching Layer
**What it does**: Stores frequently accessed data in RAM instead of hitting database.

**What to cache**:
- User sessions (already using Flask-Login, but can be faster)
- Resource prices and market data (refresh every 1-5 minutes)
- Country/region data (rarely changes)
- Leaderboards and rankings (refresh every 5-10 minutes)
- NFT metadata and bonus calculations
- Company production requirements (static data)

**Implementation**:
```python
# Flask-Caching with Redis
CACHE_TYPE = 'RedisCache'
CACHE_REDIS_HOST = 'localhost'
CACHE_REDIS_PORT = 6379
CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

# Example usage
@cache.cached(timeout=60, key_prefix='market_prices')
def get_market_prices(country_id):
    # Database query here
    pass
```

**RAM allocation**: 2-4GB for Redis

**Expected improvement**: 50-90% reduction in database queries

---

## 4. MySQL Optimization
**What it does**: Tune MySQL to use available RAM and handle concurrent connections.

**Recommended config** (`/etc/mysql/mysql.conf.d/mysqld.cnf`):
```ini
[mysqld]
# Connection handling
max_connections = 200
thread_cache_size = 16

# InnoDB Buffer Pool (main memory allocation - 50-70% of RAM after OS/Redis)
innodb_buffer_pool_size = 32G
innodb_buffer_pool_instances = 8

# Logging and recovery
innodb_log_file_size = 1G
innodb_log_buffer_size = 64M

# Query cache (for repeated identical queries)
query_cache_type = 1
query_cache_size = 256M
query_cache_limit = 2M

# Temp tables
tmp_table_size = 256M
max_heap_table_size = 256M

# Connection timeout
wait_timeout = 600
interactive_timeout = 600
```

**Expected improvement**: Much faster queries, handle 200+ concurrent DB connections

---

## 5. Database Connection Pooling
**What it does**: Reuses database connections instead of creating new ones per request.

**Implementation** (SQLAlchemy):
```python
SQLALCHEMY_POOL_SIZE = 20  # Number of connections to keep open
SQLALCHEMY_POOL_TIMEOUT = 30  # Seconds to wait for available connection
SQLALCHEMY_POOL_RECYCLE = 3600  # Recycle connections after 1 hour
SQLALCHEMY_MAX_OVERFLOW = 30  # Allow 30 extra connections during peak
```

**Expected improvement**: Faster response times, no connection exhaustion

---

## 6. Database Indexing
**What it does**: Speeds up common queries by creating lookup indexes.

**Tables to index** (based on common queries):
```sql
-- User lookups
CREATE INDEX idx_user_wallet ON user(base_wallet_address);
CREATE INDEX idx_user_country ON user(country_of_residence_id);
CREATE INDEX idx_user_citizenship ON user(citizenship_country_id);

-- Company queries
CREATE INDEX idx_company_owner ON company(owner_id);
CREATE INDEX idx_company_country ON company(country_id);
CREATE INDEX idx_company_type ON company(company_type);

-- Market queries
CREATE INDEX idx_market_item_country_resource ON country_market_item(country_id, resource_id);
CREATE INDEX idx_market_listing_resource ON market_listing(resource_id, quality, is_active);

-- NFT queries
CREATE INDEX idx_nft_user ON nft_inventory(user_id, nft_type);
CREATE INDEX idx_nft_equipped ON nft_inventory(user_id, is_equipped);

-- Employment
CREATE INDEX idx_employment_company ON employment(company_id);
CREATE INDEX idx_employment_user ON employment(user_id);
```

**Expected improvement**: 10-100x faster for indexed queries

---

## 7. Parallel Scheduler Jobs
**What it does**: Run multiple scheduler tasks in parallel using thread pools.

**Current scheduler jobs**:
- Election management (every 5 min)
- Government elections (every 5 min)
- Market price recording (daily)
- Law voting (every 10 min)
- War expiration (hourly)
- NFT regeneration (hourly)

**Optimization**:
```python
from concurrent.futures import ThreadPoolExecutor

# Use thread pool for scheduler
scheduler = BackgroundScheduler(
    executors={
        'default': ThreadPoolExecutor(max_workers=6)  # Match CPU cores
    }
)
```

**Expected improvement**: Scheduler jobs don't block each other

---

## 8. Background Task Queue (Optional - Future)
**What it does**: Offload heavy tasks to background workers.

**When to add**: If response times suffer from heavy operations.

**Tasks to offload**:
- NFT minting/blockchain interactions
- Email sending
- Complex report generation
- Bulk data processing

**Technology**: Celery + Redis

---

## 9. RAM Allocation Summary

| Component | Allocation |
|-----------|------------|
| Ubuntu OS | ~2GB |
| MySQL InnoDB Buffer | 32GB |
| MySQL other buffers | ~2GB |
| Redis cache | 4GB |
| Gunicorn workers (9 × ~500MB) | ~5GB |
| Python app overhead | ~2GB |
| **Reserved headroom** | ~17GB |
| **Total** | 64GB |

---

## 10. Monitoring (Recommended)
**Tools to install**:
- `htop` - CPU/RAM monitoring
- `iotop` - Disk I/O monitoring
- `mysqltop` - MySQL query monitoring
- `redis-cli monitor` - Redis monitoring
- Flask-DebugToolbar (dev only)
- Prometheus + Grafana (production metrics)

---

## Implementation Order

1. **Phase 1 - Basic Setup** (Before launch)
   - [ ] Install and configure Nginx
   - [ ] Configure Gunicorn with recommended settings
   - [ ] Set up MySQL with optimized config
   - [ ] Add database indexes
   - [ ] Configure SQLAlchemy connection pooling

2. **Phase 2 - Caching** (After initial load testing)
   - [ ] Install Redis
   - [ ] Add Flask-Caching
   - [ ] Cache market prices, country data, static lookups
   - [ ] Cache user session data

3. **Phase 3 - Fine-tuning** (Based on monitoring)
   - [ ] Optimize slow queries (identify with slow query log)
   - [ ] Adjust worker counts based on actual load
   - [ ] Tune cache TTLs based on data freshness needs

4. **Phase 4 - Advanced** (If needed)
   - [ ] Add Celery for background tasks
   - [ ] Set up read replicas for database
   - [ ] CDN for static assets

---

## Quick Commands for Deployment

```bash
# Install dependencies
sudo apt install nginx redis-server mysql-server

# Start services
sudo systemctl enable nginx redis mysql
sudo systemctl start nginx redis mysql

# Run Gunicorn
gunicorn -c gunicorn.conf.py "app:create_app()"

# Check MySQL status
sudo mysqladmin status

# Check Redis
redis-cli ping
```

---

## Notes
- All optimizations should be tested in staging before production
- Monitor performance metrics before and after each change
- The 1000 concurrent users target is very achievable with this hardware
- Peak hours (21:00 CET) may need slightly higher connection limits
