import redis
import json
import time
import random
import logging
import zlib
from functools import wraps
import os

# Get logger for this module
logger = logging.getLogger(__name__)

# Simple in-memory cache for fallback when Redis is not available
memory_cache = {}

class CacheService:
    """
    Centralized caching service that provides Redis caching with in-memory fallback.
    """
    
    def __init__(self):
        """Initialize the cache service with Redis if available, otherwise use in-memory cache."""
        self.redis_available = False
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection with error handling."""
        # Check if Redis is explicitly disabled via environment variable
        redis_enabled = os.environ.get('REDIS_ENABLED', 'true').lower() == 'true'
        
        if not redis_enabled:
            logger.info("Redis explicitly disabled by REDIS_ENABLED environment variable. Using in-memory cache.")
            self.redis_available = False
            self.redis_client = None
            return
            
        try:
            # Get Redis connection details from environment or use defaults
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_db = int(os.environ.get('REDIS_DB', 0))
            redis_password = os.environ.get('REDIS_PASSWORD', None)
            
            # Connect to Redis
            self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                db=redis_db,
                password=redis_password
            )
            # Test Redis connection
            self.redis_client.ping()
            self.redis_available = True
            logger.info(f"Redis cache available at {redis_host}:{redis_port}")
        except (ImportError, redis.exceptions.ConnectionError) as e:
            self.redis_available = False
            self.redis_client = None
            logger.warning(f"Redis not available: {str(e)}. Using in-memory cache.")
    
    def get(self, key):
        """Get a value from cache (Redis or in-memory)."""
        if self.redis_available and self.redis_client:
            try:
                # Verify Redis is still connected
                self.redis_client.ping()
                
                value = self.redis_client.get(key)
                if value:
                    try:
                        # Try to decompress if it's compressed data
                        if isinstance(value, bytes):
                            try:
                                decompressed = zlib.decompress(value)
                                return json.loads(decompressed)
                            except (zlib.error, json.JSONDecodeError):
                                # Not compressed or not JSON, return as is
                                return value
                        return json.loads(value)
                    except (TypeError, json.JSONDecodeError):
                        # If it's not JSON, return as is
                        return value
                return None
            except (redis.ConnectionError, redis.RedisError) as e:
                logger.error(f"Redis error: {str(e)}")
                self.redis_available = False
                # Fall through to memory cache
        
        # Use memory cache
        entry = memory_cache.get(key)
        if entry and entry['expiry'] > time.time():
            return entry['data']
        return None
    
    def set(self, key, value, ttl=3600):
        """Set a value in cache (Redis or in-memory) with TTL in seconds."""
        if self.redis_available and self.redis_client:
            try:
                # Verify Redis is still connected
                self.redis_client.ping()
                
                # Check if we need to compress (for large values)
                is_large_value = isinstance(value, (dict, list)) and len(json.dumps(value)) > 10000
                
                if is_large_value:
                    try:
                        # Compress the value to save memory
                        compressed = zlib.compress(json.dumps(value).encode('utf-8'))
                        self.redis_client.setex(key, ttl, compressed)
                        return
                    except (TypeError, json.JSONDecodeError) as e:
                        logger.error(f"Compression error: {str(e)}")
                        # Fall through to non-compressed storage
                
                # Store normally
                if isinstance(value, bytes):
                    # Store binary data directly
                    self.redis_client.setex(key, ttl, value)
                else:
                    # Convert to JSON for regular data
                    try:
                        self.redis_client.setex(key, ttl, json.dumps(value))
                    except (TypeError, json.JSONDecodeError) as e:
                        logger.error(f"JSON serialization error: {str(e)}")
                        # Cannot store this value
                
                return
            except (redis.ConnectionError, redis.RedisError) as e:
                logger.error(f"Redis error: {str(e)}")
                self.redis_available = False
                # Fall through to memory cache
        
        # Use memory cache
        memory_cache[key] = {
            'data': value,
            'expiry': time.time() + ttl
        }
        
        # Garbage collection for memory cache (random probability to avoid overhead)
        if random.random() < 0.01:  # 1% chance on each cache set
            self._cleanup_memory_cache()
    
    def _cleanup_memory_cache(self):
        """Remove expired items from memory cache."""
        now = time.time()
        expired_keys = [k for k, v in memory_cache.items() if v['expiry'] < now]
        for k in expired_keys:
            del memory_cache[k]
    
    def delete(self, key):
        """Delete a key from cache."""
        if self.redis_available and self.redis_client:
            try:
                self.redis_client.delete(key)
            except (redis.ConnectionError, redis.RedisError) as e:
                logger.error(f"Redis error in delete: {str(e)}")
        
        if key in memory_cache:
            del memory_cache[key]
    
    def flush(self):
        """Flush all cache."""
        if self.redis_available and self.redis_client:
            try:
                self.redis_client.flushdb()
            except (redis.ConnectionError, redis.RedisError) as e:
                logger.error(f"Redis error in flush: {str(e)}")
        
        memory_cache.clear()


# Singleton instance
cache_service = CacheService()

def cache_response(ttl=3600):
    """
    Decorator to cache API responses
    
    Args:
        ttl (int): Time-to-live for cache in seconds. Default 1 hour.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(username, *args, **kwargs):
            # Check if we should disable caching
            is_dev_mode = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('DISABLE_CACHE') == 'true'
            
            if is_dev_mode:
                # In development mode, skip caching and call the function directly
                logger.info(f"Caching disabled in development mode for {func.__name__}")
                return func(username, *args, **kwargs)
            
            cache_key = f"{func.__name__}:{username}:{json.dumps(args)}:{json.dumps(kwargs, sort_keys=True)}"
            
            # Check if result is in cache
            cached_result = cache_service.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Cache miss, call the function
            result = func(username, *args, **kwargs)
            
            # Only cache successful results
            if result and not (isinstance(result, dict) and 'error' in result):
                cache_service.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator 