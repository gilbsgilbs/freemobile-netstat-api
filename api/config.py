import os

import pytz

IS_4G_THRESHOLD = 24 * 60 * 60 * 1000
TIMEZONE = pytz.timezone('Europe/Paris')
DB_HOST = os.getenv('FMNS_DB_HOST', None)
DB_USER = os.getenv('FMNS_DB_USER', None)
DB_PASSWORD = os.getenv('FMNS_DB_PASSWORD', None)
DB_NAME = 'fmns-api'
DAILY_STATS_CAP_SIZE = 30 * (10 ** 9)
DEVICES_CAP_SIZE = 10 * (10 ** 9)
MEMCACHED_SERVERS = ['127.0.0.1:11211']