# Tactizen API

## Status: DISABLED BY DEFAULT

The Tactizen API is currently **disabled**. Follow the instructions below to enable it when needed.

## Enabling the API

### Method 1: Environment Variable (Recommended)

Add to your `.env` file:
```bash
API_ENABLED=true
```

Then restart the application:
```bash
flask run
```

### Method 2: Temporary Enable (Development)

Set the environment variable for a single session:

**Windows:**
```cmd
set API_ENABLED=true
flask run
```

**Linux/Mac:**
```bash
export API_ENABLED=true
flask run
```

### Method 3: Configuration Override

Edit `config.py` and set:
```python
API_ENABLED = True
```

**Note**: This overrides the environment variable.

---

## Quick Start

### 1. Enable the API
Follow one of the methods above to enable API endpoints.

### 2. Create an API Token

**Via Web UI:**
1. Log in to your account
2. Navigate to `/api/tokens`
3. Click "Create New Token"
4. Select required scopes (permissions)
5. Copy the token (shown only once!)

**Important**: Save the token securely - it won't be shown again.

### 3. Make API Requests

Use the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer tac_your_token_here" \
     https://tactizen.com/api/v1/profile
```

---

## API Endpoints

### Authentication

All API endpoints (except `/api/v1/info`) require authentication.

**Authentication Methods** (in priority order):
1. **Authorization header** (recommended):
   ```
   Authorization: Bearer tac_abc123...
   ```

2. **X-API-Key header**:
   ```
   X-API-Key: tac_abc123...
   ```

3. **Query parameter** (discouraged, less secure):
   ```
   ?api_key=cr_abc123...
   ```

### Available Endpoints

#### Public
- `GET /api/v1/info` - API information (no auth required)

#### Profile
- `GET /api/v1/profile` - Get your profile (requires `read:profile`)
- `GET /api/v1/profile/stats` - Get detailed stats (requires `read:stats`)

#### Inventory
- `GET /api/v1/inventory` - Get your inventory (requires `read:inventory`)

#### Countries
- `GET /api/v1/countries` - List all countries
- `GET /api/v1/countries/{id}` - Get country details

#### Market
- `GET /api/v1/market` - Get market listings (requires `read:market`)

#### Token Management
- `GET /api/v1/tokens` - List your API tokens
- `GET /api/v1/tokens/{id}` - Get token details
- `POST /api/v1/tokens/{id}/revoke` - Revoke a token

#### Admin (requires admin scopes)
- `GET /api/v1/admin/users` - List all users
- `GET /api/v1/admin/stats` - Get system statistics

---

## Token Scopes (Permissions)

Tokens must have appropriate scopes for the endpoints they access:

### Read Scopes
- `read:profile` - View profile information
- `read:inventory` - View inventory
- `read:market` - View market listings
- `read:messages` - View messages
- `read:stats` - View detailed statistics

### Write Scopes
- `write:market` - Create/modify market listings
- `write:messages` - Send messages
- `write:actions` - Perform game actions (work, train, travel)

### Admin Scopes
- `admin:read` - Read admin data
- `admin:write` - Perform admin actions

### Special Scopes
- `full:access` - All permissions (use with caution!)

---

## Examples

### Get Your Profile

```bash
curl -H "Authorization: Bearer tac_abc123..." \
     https://tactizen.com/api/v1/profile
```

Response:
```json
{
  "data": {
    "id": 42,
    "username": "john_doe",
    "level": 15,
    "xp": 12500,
    "citizenship": {
      "country_id": 1,
      "country_name": "United States"
    }
  }
}
```

### Get Your Inventory

```bash
curl -H "Authorization: Bearer tac_abc123..." \
     https://tactizen.com/api/v1/inventory
```

Response:
```json
{
  "data": {
    "items": [
      {
        "resource_id": 1,
        "resource_name": "Bread",
        "quantity": 10,
        "quality": 5
      }
    ],
    "total_items": 1
  }
}
```

### List Countries (with pagination)

```bash
curl -H "Authorization: Bearer tac_abc123..." \
     "https://tactizen.com/api/v1/countries?page=1&per_page=10"
```

Response:
```json
{
  "data": [
    {
      "id": 1,
      "name": "United States",
      "currency_code": "USD",
      "tax_rate": 0.15
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total_items": 50,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## Rate Limits

API endpoints have stricter rate limits than the web interface:

- **Read endpoints**: 200 requests/hour
- **Write endpoints**: 50 requests/hour
- **Admin endpoints**: 500 requests/hour
- **Default**: 100 requests/hour

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 195
X-RateLimit-Reset: 1234567890
```

---

## Error Responses

All API errors follow this format:

```json
{
  "error": {
    "code": 401,
    "message": "Authentication required",
    "details": "No API token provided"
  }
}
```

### Common Error Codes

- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Rate Limit Exceeded
- `500` - Internal Server Error
- `503` - Service Unavailable (API disabled)

---

## Security Best Practices

### 1. Keep Tokens Secret
- Never commit tokens to version control
- Don't share tokens publicly
- Store tokens securely (environment variables, secrets manager)

### 2. Use Minimal Scopes
- Only grant permissions needed for the task
- Create separate tokens for different applications
- Use read-only tokens when possible

### 3. Rotate Tokens Regularly
- Create new tokens periodically
- Revoke old tokens
- Set expiration dates when creating tokens

### 4. Monitor Token Usage
- Check "last used" timestamp
- Review total request count
- Check for unauthorized IP addresses (if using IP whitelist)

### 5. Revoke Compromised Tokens Immediately
- If a token is exposed, revoke it immediately
- Create a new token with different scopes
- Review security logs for suspicious activity

---

## IP Whitelisting

For additional security, you can restrict tokens to specific IP addresses:

1. When creating a token, specify allowed IPs
2. Token will only work from those IPs
3. Requests from other IPs will be rejected and logged

**Example**: Restrict token to office IP:
```
Allowed IPs: 203.0.113.10, 198.51.100.20
```

---

## Disabling the API

To disable the API:

1. Remove `API_ENABLED=true` from `.env`
2. Or set `API_ENABLED=false`
3. Restart the application

All API endpoints will return `503 Service Unavailable`.

Existing tokens remain in the database but cannot be used while API is disabled.

---

## Support & Documentation

- **Full API Documentation**: `/api/docs` (when API is enabled)
- **Token Management**: `/api/tokens`
- **Security Logs**: Contact admin for access
- **Issues**: Report at GitHub repository

---

## Technical Details

### Token Format
- Prefix: `tac_` (Tactizen)
- Length: 36 characters total
- Example: `tac_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### Token Storage
- Tokens are hashed (SHA-256) before storage
- Only the hash is stored in database
- Original token cannot be recovered

### Authentication Flow
1. Extract token from request
2. Hash the token
3. Look up hash in database
4. Verify token is active and not expired
5. Check IP whitelist (if configured)
6. Verify required scopes
7. Record usage statistics
8. Allow request to proceed

---

**Last Updated**: 2025-11-15
**API Version**: 1.0
**Status**: Disabled by default
