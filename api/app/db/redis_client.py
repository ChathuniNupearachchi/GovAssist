"""Redis connection — Phase 6.10's hot session cache is the first real
job Redis has in this stack; Phase 1 wired it into docker-compose but
nothing used it until now.

Reads REDIS_URL from the environment, same convention as
`app.db.session`'s DATABASE_URL. `decode_responses=True` so callers get
`str`, not `bytes`, back — every value this module stores is JSON text.
"""

import os
from functools import lru_cache

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ["REDIS_URL"]


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)
