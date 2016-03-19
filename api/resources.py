import datetime
import re

from werkzeug import exceptions as HTTPException
from flask_restful import Resource
from cerberus import Validator
from flask import request

from api import config, model
from api.db import ConnectedMixin
from api.cache import CacheMixin
from api.utils import switch_dict_keys_to_snake, datetime_to_epoch, to_snake_case


class InfoService(Resource):
    """
    Provides information about the health of the API.
    """
    @staticmethod
    def status():
        return {'status': 'ok'}

    def get(self):
        return self.status()

    def head(self):
        return self.status()


def validate(schema):
    """
    Validate the request
    :param schema: The Cerberus schema
    """
    def validator(function):
        def wrapper(*args, **kwargs):
            query_parameters = request.json

            if not query_parameters:
                raise HTTPException.BadRequest('You must provide query parameters.')

            cerberus_validator = Validator(schema)
            if not cerberus_validator.validate(query_parameters):
                return cerberus_validator.errors, 400

            return function(*args, params=query_parameters, **kwargs)
        return wrapper
    return validator


class Device(Resource, ConnectedMixin):
    """
    A device represents a physical device.
    """
    _device_schema = {
        'brand': {'type': 'string', 'required': True, },
        'model': {'type': 'string', 'required': True, },
    }
    
    @validate(_device_schema)
    def put(self, device_id, params):
        """
        Declare a new device
        """
        device = model.Device.objects(device_identifier=device_id).first()
        if device:
            raise HTTPException.Conflict('The provided device id already exists in database.')

        device = model.Device(device_identifier=device_id, brand=params['brand'], model=params['model'])
        device.save()

        return device.as_resource(), 201


class DeviceStat(Resource, ConnectedMixin):
    """
    A device stat is a 24h statistics summary for a Device.
    """
    NB_MILLISECONDS_IN_ONE_DAY = 60 * 60 * 24 * 1000
    _device_stat_schema = {
        'timeOnOrange':
            {'type': 'integer', 'required': True, 'min': 0, 'max': NB_MILLISECONDS_IN_ONE_DAY, },
        'timeOnFreeMobile':
            {'type': 'integer', 'required': True, 'min': 0, 'max': NB_MILLISECONDS_IN_ONE_DAY, },
        'timeOnFreeMobile3g':
            {'type': 'integer', 'required': True, 'min': 0, 'max': NB_MILLISECONDS_IN_ONE_DAY, },
        'timeOnFreeMobile4g':
            {'type': 'integer', 'required': True, 'min': 0, 'max': NB_MILLISECONDS_IN_ONE_DAY, },
        'timeOnFreeMobileFemtocell':
            {'type': 'integer', 'required': True, 'min': 0, 'max': NB_MILLISECONDS_IN_ONE_DAY, },
    }

    @staticmethod
    def _date_to_datetime(date):
        """
        Validate the date format
        """
        try:
            if not len(date) == 8:
                raise ValueError
            return datetime.datetime.strptime(date, '%Y%m%d')
        except ValueError:
            raise HTTPException.BadRequest('Wrong date format.')

    @staticmethod
    def _assert_stats_consistent(stat_datetime, params):
        """
        Assert that provided stats are consistent and meaningful
        :return An error that should not raise an HTTP error or None if everything is correct.
        """
        stat_epoch = datetime_to_epoch(stat_datetime.replace(tzinfo=config.TIMEZONE)) * 1000
        min_epoch = datetime_to_epoch(datetime.datetime.now(config.TIMEZONE).replace(hour=0, minute=0, second=0,
                                                                                     microsecond=0) -
                                      datetime.timedelta(days=7)) * 1000
        max_epoch = datetime_to_epoch(datetime.datetime.now(config.TIMEZONE)
                                      .replace(hour=0, minute=0, second=0, microsecond=0)) * 1000

        total = params['timeOnOrange'] + params['timeOnFreeMobile']
        total_free_mobile = (params['timeOnFreeMobile3g'] + params['timeOnFreeMobile4g'] +
                             params['timeOnFreeMobileFemtocell'])

        if stat_epoch < min_epoch:
            return {'status': 'Ignored.', 'reason': 'too_old_statistics'}, 200
        if stat_epoch > max_epoch or total_free_mobile > params['timeOnFreeMobile'] or total_free_mobile > total:
            raise HTTPException.BadRequest('Invalid statistics.')

        return None

    @staticmethod
    def _get_device_or_raise(device_id):
        """
        Assert that the provided device identifier exists
        """
        device = model.Device.objects(device_identifier=device_id).first()
        if not device:
            raise HTTPException.NotFound('Device not found.')
        return device

    @staticmethod
    def _statistics_already_uploaded(device_id, date):
        """
        :return True if the statistic already exists in the database.
        """
        daily_device_stat = model.DailyDeviceStat.objects(device_identifier=device_id, date=date).first()
        return bool(daily_device_stat)

    @staticmethod
    def _is_device_4g(device):
        """
        :return bool: True if the device is 4g
        """
        return model.DailyDeviceStat.objects(
            device_model=device.model, device_brand=device.brand
        ).aggregate_sum('time_on_free_mobile_4g') > config.IS_4G_THRESHOLD

    @staticmethod
    def _get_or_create_stat_summary(date):
        """
        Return the DailyStatSummary of date if it exists. If it does not exists, it creates and returns it.
        """
        stat_summary = model.DailyStatSummary.objects(date=date).first()
        if stat_summary:
            return stat_summary
        return model.DailyStatSummary(date=date)

    @staticmethod
    def _callback_on_attr(obj, name, call):
        """
        Updates object obj's attribute name, calling call on it.

        Example:
            obj.foo = 0
            _callback_on_attr(obj, 'foo', lambda foo_value: foo_value + 1)
            assert obj.foo == 1

        :param obj: An object
        :param name: Attribute name to update
        :param call: The callable that will be called on attribute name
        """
        old_val = getattr(obj, name)
        setattr(obj, name, call(old_val))

    @validate(_device_stat_schema)
    def post(self, device_id, date, params):
        """
        Post a daily device statistics.
        """
        stat_datetime = self._date_to_datetime(date)

        error = self._assert_stats_consistent(stat_datetime, params)
        if error:
            return error

        device = self._get_device_or_raise(device_id)

        if self._statistics_already_uploaded(device_id, date):
            return {'status': 'Statistics already uploaded.'}, 200

        # Save daily device stat
        params['deviceIdentifier'] = device_id
        params['deviceBrand'] = device.brand
        params['deviceModel'] = device.model
        params['date'] = date
        params['is4g'] = self._is_device_4g(device)
        daily_device_stat = model.DailyDeviceStat(**switch_dict_keys_to_snake(params))
        daily_device_stat.save()

        # Update stat summary
        daily_stat_summary = self._get_or_create_stat_summary(date)
        for stat_global in ('timeOnOrange', 'timeOnFreeMobile', 'timeOnFreeMobileFemtocell', ):
            self._callback_on_attr(daily_stat_summary.stats_global, to_snake_case(stat_global),
                                   lambda old_duration: old_duration + params[stat_global])
        # Femtocell is a "network type", hence it is already included in time_on_freemobile. We must subtract it.
        daily_stat_summary.stats_global.time_on_free_mobile -= params['timeOnFreeMobileFemtocell']

        for stat_4g in ('timeOnOrange', 'timeOnFreeMobile3g', 'timeOnFreeMobile4g', 'timeOnFreeMobileFemtocell', ):
            self._callback_on_attr(daily_stat_summary.stats_4g, to_snake_case(stat_4g),
                                   lambda old_duration: old_duration + params[stat_4g])
        daily_stat_summary.save()

        return daily_device_stat.as_resource()


class NetworkUsageChart(Resource, ConnectedMixin, CacheMixin):
    """
    Provide aggregated statistics
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CacheMixin.__init__(self)

    @staticmethod
    def _assert_valid_date_range(start_date, end_date):
        date_regex = re.compile('^\d{8}$')
        if not date_regex.match(start_date) or not date_regex.match(end_date):
            raise HTTPException.BadRequest('Date must me in `YYYYMMDD` format.')
        if end_date < start_date:
            raise HTTPException.BadRequest('Start date must be lower than end date.')
        if end_date > datetime.datetime.now(tz=config.TIMEZONE).strftime("%Y%m%d"):
            raise HTTPException.BadRequest('End date can\'t be in the future.')

    @staticmethod
    def _query_stat_aggregation(key, start_date, end_date, only_4g=False):
        """
        Query a stat aggregation on the whole database.
        """
        if only_4g:
            key = 'stats_4g.' + key
        else:
            key = 'stats_global.' + key

        return model.DailyStatSummary.objects(
            date__gte=start_date, date__lte=end_date
        ).aggregate_sum(key)

    @staticmethod
    def _count_distinct_users(start_date, end_date, only_4g=False):
        """
        Count distinct users.
        """
        extra_params = {}
        if only_4g:
            extra_params['is_4g'] = True

        pipeline = [
            {'$group': {'_id': '$device_identifier'}},
            {'$group': {'_id': 1, 'count': {'$sum': 1}}},
        ]

        aggregation = [
            aggregate for aggregate in
            model.DailyDeviceStat.objects(
                date__gte=start_date, date__lte=end_date, **extra_params
            ).aggregate(*pipeline)
        ]

        if not aggregation:
            return 0

        return aggregation[0]['count']

    @staticmethod
    def _str_date(dt):
        """
        Convert a offset-aware datetime to a YYYYMMDD string.
        """
        return dt.strftime("%Y%m%d")

    def get(self):
            """
            Retrieve all statistics
            """
            default_start_date = self._str_date(datetime.datetime.now(tz=config.TIMEZONE) - datetime.timedelta(days=6))
            default_end_date = self._str_date(datetime.datetime.now(tz=config.TIMEZONE))

            start_date = request.args.get('start_date', default_start_date)
            end_date = request.args.get('end_date', default_end_date)

            self._assert_valid_date_range(start_date, end_date)

            stats = self.cache.get(start_date + '-' + end_date)
            if stats is not None:
                return stats

            stats = {
                'stats_global': {
                    'time_on_orange':
                        self._query_stat_aggregation('time_on_orange', start_date, end_date),
                    'time_on_free_mobile':
                        # We have to subtract the time on femtocell, since femtocell is already included in free mobile
                        self._query_stat_aggregation('time_on_free_mobile', start_date, end_date),
                    'time_on_free_mobile_femtocell':
                        self._query_stat_aggregation('time_on_free_mobile_femtocell', start_date, end_date),
                    'users':
                        self._count_distinct_users(start_date, end_date),
                },
                'stats_4g': {
                    'time_on_orange':
                        self._query_stat_aggregation('time_on_orange', start_date, end_date, only_4g=True),
                    'time_on_free_mobile':
                        self._query_stat_aggregation('time_on_free_mobile', start_date, end_date, only_4g=True),
                    'time_on_free_mobile_3g':
                        self. _query_stat_aggregation('time_on_free_mobile_3g', start_date, end_date, only_4g=True),
                    'time_on_free_mobile_4g':
                        self._query_stat_aggregation('time_on_free_mobile_4g', start_date, end_date, only_4g=True),
                    'time_on_free_mobile_femtocell':
                        self._query_stat_aggregation(
                            'time_on_free_mobile_femtocell', start_date, end_date, only_4g=True
                        ),
                    'users':
                        self._count_distinct_users(start_date, end_date, only_4g=True),
                },
            }

            if default_start_date <= end_date:
                # Cache one hour if stat is less than one week old
                self.cache.set(start_date + '-' + end_date, stats, timeout=60 * 60)
            else:
                # Cache forever otherwise because it cannot change again.
                self.cache.set(start_date + '-' + end_date, stats, timeout=0)

            return stats
