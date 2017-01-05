import datetime

import mongoengine
from werkzeug import exceptions as HTTPException
from flask_restful import Resource
from cerberus import Validator
from flask import request

from api import config, model
from api.db import ConnectedMixin
from api.cache import CacheMixin
from api.utils import switch_dict_keys_to_snake, datetime_to_epoch, datetime_to_date_string, \
    date_string_to_datetime, check_valid_date_range


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


class Device(ConnectedMixin, Resource):
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


class DeviceStat(ConnectedMixin, Resource):
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
        Validate the date format and return a datetime
        """
        try:
            return date_string_to_datetime(date)
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
        ).sum('time_on_free_mobile_4g') > config.IS_4G_THRESHOLD

    @staticmethod
    def _get_or_create_stat_summary(date):
        """
        Get or create a DailyStatSummary.

        :param date: The date of the DailyStatSummary
        :type date: str
        """
        try:
            # Always try to insert the StatSummary to avoid errors on concurrent inserts
            model.DailyStatSummary(date=date).save(force_insert=True)
        except mongoengine.errors.NotUniqueError:
            pass
        return model.DailyStatSummary.objects(date=date).first()

    def _update_daily_stat_summary(self, date, params):
        """
        Update the daily stat summary.
        :param date: The date of the daily stat summary (in YYYYMMDD format)
        :type date: string
        :param params: The query parameters
        :type params: dict
        """
        daily_stat_summary = self._get_or_create_stat_summary(date)

        daily_stat_summary.stats_global.modify(
            inc__time_on_orange=params['timeOnOrange'],
            # Femtocell is a "network type", hence it is already included in time_on_free_mobile. We must subtract it.
            inc__time_on_free_mobile=params['timeOnFreeMobile'] - params['timeOnFreeMobileFemtocell'],
            inc__time_on_free_mobile_femtocell=params['timeOnFreeMobileFemtocell'],
        )

        daily_stat_summary.stats_4g.modify(
            inc__time_on_orange=params['timeOnOrange'],
            inc__time_on_free_mobile_3g=params['timeOnFreeMobile3g'],
            inc__time_on_free_mobile_4g=params['timeOnFreeMobile4g'],
            inc__time_on_free_mobile_femtocell=params['timeOnFreeMobileFemtocell'],
        )

        daily_stat_summary.save()

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
            # We return a 200 here instead of a 409 because a 409 would make the device retry
            return {'status': 'Statistics already uploaded.'}, 200

        # Save daily device stat
        params.update({
            'deviceIdentifier': device_id,
            'deviceBrand': device.brand,
            'deviceModel': device.model,
            'date': date,
            'is4g': self._is_device_4g(device),
        })
        daily_device_stat = model.DailyDeviceStat(**switch_dict_keys_to_snake(params))
        daily_device_stat.save()

        self._update_daily_stat_summary(date, params)

        return daily_device_stat.as_resource()


class DailyNetworkUsageChart(ConnectedMixin, Resource):
    """
    Provide bulk statistics of the network usage over time.
    """
    @staticmethod
    def _get_stats(start_date, end_date):
        """
        Get the statistics over a period.
        """
        daily_stat_summary_query = model.DailyStatSummary.objects(
            date__gte=start_date, date__lte=end_date
        )

        stats = {
            'stats_global': [],
            'stats_4g': [],
        }
        for daily_stat_summary in daily_stat_summary_query:
            daily_stat_summary_dictionary = daily_stat_summary.to_mongo()
            stats_global = daily_stat_summary_dictionary['stats_global']
            stats_4g = daily_stat_summary_dictionary['stats_4g']

            stats['stats_global'].append(stats_global)
            stats['stats_4g'].append(stats_4g)

        return stats

    @staticmethod
    def _assert_valid_date_range(start_date, end_date):
        """
        Assert that a given date range is consistent.
        """
        is_valid, error = check_valid_date_range(start_date, end_date, tz=config.TIMEZONE)
        if not is_valid:
            raise HTTPException.BadRequest(error)

    def get(self):
        """
        Retrieve all statistics
        """
        default_start_date = datetime_to_date_string(
            datetime.datetime.now(tz=config.TIMEZONE) - datetime.timedelta(days=6)
        )
        default_end_date = datetime_to_date_string(
            datetime.datetime.now(tz=config.TIMEZONE)
        )

        start_date = request.args.get('start_date', default_start_date)
        end_date = request.args.get('end_date', default_end_date)

        self._assert_valid_date_range(start_date, end_date)

        return self._get_stats(start_date, end_date)


class NetworkUsageChart(ConnectedMixin, CacheMixin, Resource):
    """
    Provide aggregated statistics between Orange and FM.
    """
    # Above this date range, an exception will be raised. This prevents computing stats over
    # too much documents, which could freeze the API and the database.
    _MAX_DATE_RANGE_DAYS = 31

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CacheMixin.__init__(self)

    @staticmethod
    def _assert_maximum_timedelta(start_date_string, end_date_string, max_days):
        """
        Assert that the timedelta between start_date and end_date does not exceed max_days
        """
        try:
            start_date_dt = date_string_to_datetime(start_date_string)
            end_date_dt = date_string_to_datetime(end_date_string)
        except ValueError:
            raise HTTPException.BadRequest('Wrong date format.')

        if datetime.timedelta(days=max_days) <= end_date_dt - start_date_dt:
            raise HTTPException.BadRequest('Too long date range (maximum is {} days).'.format(max_days))

    @staticmethod
    def _assert_valid_date_range(start_date, end_date):
        is_valid, error = check_valid_date_range(start_date, end_date, tz=config.TIMEZONE)
        if not is_valid:
            raise HTTPException.BadRequest(error)
        NetworkUsageChart._assert_maximum_timedelta(start_date, end_date, NetworkUsageChart._MAX_DATE_RANGE_DAYS)

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
        ).sum(key)

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

    def get(self):
            """
            Retrieve all statistics
            """
            default_start_date = datetime_to_date_string(
                datetime.datetime.now(tz=config.TIMEZONE) - datetime.timedelta(days=6)
            )
            default_end_date = datetime_to_date_string(
                datetime.datetime.now(tz=config.TIMEZONE)
            )

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
                    timeout = 60 * 60
            else:
                # Cache forever otherwise because it cannot change again.
                timeout = 0
            self.cache.set(start_date + '-' + end_date, stats, timeout=timeout)

            return stats
