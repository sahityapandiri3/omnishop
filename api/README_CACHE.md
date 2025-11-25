# Store Discovery API Caching

This document explains the caching mechanism for the store discovery API and how to use it.

## Overview

The store discovery API (`/api/stores`) has been optimized with a 24-hour in-memory cache to improve performance. Instead of querying the database on every request, the API now serves results from a cache that expires after 24 hours.

## Benefits

- **Faster Response Times**: Cached responses return instantly without database queries
- **Reduced Database Load**: Fewer queries to the database, especially during high traffic
- **Improved User Experience**: The frontend loads store filters immediately

## How It Works

### Architecture

The caching system uses a simple module-level cache with these components:

1. **In-Memory Cache**: Stores the list of available stores
2. **Cache Timestamp**: Tracks when the cache was last updated
3. **24-Hour TTL**: Cache expires after 24 hours
4. **Automatic Fallback**: If cache is expired or missing, automatically queries database

### Cache Flow

```
┌─────────────┐
│ GET /stores │
└──────┬──────┘
       │
       ▼
  ┌─────────┐
  │ Is      │
  │ cached? │◄─── Cache valid for 24 hours
  └────┬────┘
       │
  ┌────┴────┐
  │         │
  ▼         ▼
YES       NO
  │         │
  │         ▼
  │    Query DB
  │         │
  │         ▼
  │    Update Cache
  │         │
  └────┬────┘
       │
       ▼
 Return Stores
```

## API Endpoints

### GET /api/stores

Returns the list of available stores (from cache if available).

**Response:**
```json
{
  "stores": ["fleck", "josmo", "magari", ...]
}
```

### POST /api/stores/warm-cache

Warms the cache by fetching and caching the store list. This endpoint should be called after each deployment.

**Response:**
```json
{
  "success": true,
  "message": "Cache warmed successfully with 11 stores at 2025-11-24 16:04:56.902598",
  "stores": ["fleck", "josmo", "magari", ...]
}
```

## Usage

### Local Development

```bash
# Start the API server
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Warm the cache
python3 scripts/warm_cache.py
```

### Production Deployment

After each deployment to production, warm the cache:

```bash
# Using the Python script
python3 scripts/warm_cache.py --url https://your-production-url.com

# Or using curl directly
curl -X POST https://your-production-url.com/api/stores/warm-cache
```

## Configuration

### Cache TTL

The cache Time-To-Live (TTL) is set to 24 hours by default. To change this, modify the `_cache_ttl` variable in `/api/routers/stores.py`:

```python
# Current setting (24 hours)
_cache_ttl = timedelta(hours=24)

# Example: Change to 12 hours
_cache_ttl = timedelta(hours=12)

# Example: Change to 2 hours
_cache_ttl = timedelta(hours=2)
```

## Files Modified

- **`/api/routers/stores.py`**: Main stores router with caching logic
- **`/api/scripts/warm_cache.py`**: Script to warm the cache after deployment

## Implementation Details

### Cache Storage

The cache uses module-level variables:

```python
_stores_cache: Optional[List[str]] = None      # Cached store list
_cache_timestamp: Optional[datetime] = None   # When cache was last updated
_cache_ttl = timedelta(hours=24)              # Cache expiry time
```

### Cache Validation

```python
def _is_cache_valid() -> bool:
    """Check if the cache is valid (not expired)"""
    if _stores_cache is None or _cache_timestamp is None:
        return False

    age = datetime.now() - _cache_timestamp
    return age < _cache_ttl
```

## Monitoring

To verify the cache is working, check the API logs. You should see:

```
Returning cached stores (cached at 2025-11-24 16:04:56.902598)
```

If the cache is being warmed or refreshed:

```
Warming stores cache...
✅ Cache warmed successfully with 11 stores
```

## Troubleshooting

### Cache Not Working

1. **Check if the API server restarted**: The cache is in-memory, so it's lost on restart
2. **Warm the cache manually**: Run `python3 scripts/warm_cache.py`
3. **Check the logs**: Look for cache-related messages

### Stale Data

If you add new stores to the database:
- The cache will automatically refresh after 24 hours
- OR manually warm the cache: `curl -X POST /api/stores/warm-cache`

### Performance Issues

If the stores endpoint is still slow:
1. Check if the database query is the bottleneck
2. Consider reducing the cache TTL
3. Check for other performance issues in the stack

## Future Enhancements

Potential improvements for the future:

1. **Redis Cache**: Use Redis instead of in-memory cache for multi-instance deployments
2. **Cache Invalidation**: Add endpoints to manually invalidate the cache
3. **Metrics**: Add cache hit/miss metrics for monitoring
4. **Preemptive Refresh**: Refresh cache before expiry to avoid cold starts
