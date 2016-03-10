from api import config
from mongoengine import connect


class ConnectedMixin:
    """
    Initiates a connection to MongoDB
    """
    def __init__(self):
        connect(config.DB_NAME, host=config.DB_HOST, username=config.DB_USER, password=config.DB_PASSWORD)
