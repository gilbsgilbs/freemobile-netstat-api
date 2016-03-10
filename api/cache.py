from werkzeug.contrib.cache import MemcachedCache

from api import config


class CacheMixin:
    """
    Provides caching facility
    """
    def __init__(self):
        self.cache = MemcachedCache(config.MEMCACHED_SERVERS)
