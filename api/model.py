from abc import ABCMeta
import datetime

from bson import Int64
from mongoengine import (Document, DateTimeField, StringField, BooleanField, EmbeddedDocument, EmbeddedDocumentField,
                         LongField)

from api import config


class FMNSDocument(Document):
    """
    Base abstract document for FMNS documents
    """
    __metaclass__ = ABCMeta

    added = DateTimeField(default=datetime.datetime.now, required=True)
    modified = DateTimeField(default=datetime.datetime.now, required=True)

    meta = {
        'allow_inheritance': True,
        'abstract': True,
    }

    def save(self, *args, **kwargs):
        self.modified = datetime.datetime.now()

        super(FMNSDocument, self).save(*args, **kwargs)

    def as_resource(self):
        """
        Return the model as a resource dict
        """
        mongo_obj = dict(self.to_mongo())
        del mongo_obj['_id']
        mongo_obj['type'] = mongo_obj.pop('_cls')

        def _datetime_as_string(dic):
            """
            Convert datetimes to strings in a dictionary (destructive, no copy).
            """
            for k, v in dic.items():
                if isinstance(v, dict):
                    dic[k] = _datetime_as_string(v)
                elif isinstance(v, datetime.datetime):
                    dic[k] = str(v)

            return dic

        return _datetime_as_string(mongo_obj)


class DailyDeviceStat(FMNSDocument):
    """
    Daily statistic representation for a device
    """
    device_identifier = StringField(required=True)
    device_brand = StringField(required=True)
    device_model = StringField(required=True)
    is_4g = BooleanField(default=False, required=True)

    time_on_orange = LongField(default=0, required=True)
    time_on_free_mobile = LongField(default=0, required=True)
    time_on_free_mobile_3g = LongField(default=0, required=True)
    time_on_free_mobile_4g = LongField(default=0, required=True)
    time_on_free_mobile_femtocell = LongField(default=0, required=True)

    date = StringField(required=True, unique_with='device_identifier')

    meta = {
        'indexes': [
            ('device_identifier', '-date', ),
            ('device_model', 'device_brand', 'time_on_free_mobile_4g', ),
            ('-date', 'is_4g', 'device_identifier', ),
        ],
        'max_size': config.DAILY_DEVICE_STATS_CAP_SIZE,
    }


class DailyStatSummary(FMNSDocument):
    """
    Daily statistic representation for whole devices.
    It's just an optimization to prevent aggregating on the whole DailyDeviceStats.
    """
    class StatsGlobal(EmbeddedDocument):
        time_on_orange = LongField(default=0, required=True)
        time_on_free_mobile = LongField(default=0, required=True)
        time_on_free_mobile_femtocell = LongField(default=0, required=True)

    class Stats4G(EmbeddedDocument):
        time_on_orange = LongField(default=0, required=True)
        time_on_free_mobile_3g = LongField(default=0, required=True)
        time_on_free_mobile_4g = LongField(default=0, required=True)
        time_on_free_mobile_femtocell = LongField(default=0, required=True)

    stats_global = EmbeddedDocumentField(StatsGlobal, default=StatsGlobal)
    stats_4g = EmbeddedDocumentField(Stats4G, default=Stats4G)

    date = StringField(required=True, unique=True)

    meta = {
        'indexes': [
            ('-date', ),
        ],
        'max_size': config.DAILY_STAT_SUMMARY_CAP_SIZE,
    }


class Device(FMNSDocument):
    """
    Physical device representation
    """
    device_identifier = StringField(required=True, unique=True)
    brand = StringField(required=True)
    model = StringField(required=True)

    meta = {
        'indexes': [
            ('device_identifier', 'brand', 'model'),
        ],
        'max_size': config.DEVICES_CAP_SIZE,
    }
