import redis
import os
from dotenv import load_dotenv

load_dotenv()

# Check for REDIS_URL in env, else default
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

def get_redis_client():
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True # String responses instead of bytes
        )
        # Test connection
        r.ping()
        return r
    except redis.ConnectionError as e:
        print(f"Error connecting to Redis: {e}")
        return None

def set_value(key: str, value: str, expiration: int = None):
    r = get_redis_client()
    if r:
        r.set(key, value, ex=expiration)

def get_value(key: str):
    r = get_redis_client()
    if r:
        return r.get(key)
    return None
