import datetime
import pytz
import re


def _callback_on_all_dict_keys(dt, callback_fn):
    """
    Callback callback_fn on all dictionary keys recursively
    """
    result = {}
    for (key, val) in dt.items():
        if type(val) == dict:
            val = _callback_on_all_dict_keys(val, callback_fn)
        result[callback_fn(key)] = val
    return result


def to_snake_case(camel_str):
    """
    Convert a string to snake case
    """
    snake = re.sub('(.)([A-Z0-9][a-z]+)', r'\1_\2', camel_str)
    return re.sub('([a-z0-9])([A-Z0-9])', r'\1_\2', snake).lower()


def switch_dict_keys_to_snake(dt):
    """
    Convert dict keys to snake case
    """
    return _callback_on_all_dict_keys(dt, to_snake_case)


def to_camel_case(snake_str):
    """
    Convert a string to camel case
    """
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def switch_dict_keys_to_camel(dt):
    """
    Convert dict keys to camel case
    """
    return _callback_on_all_dict_keys(dt, to_camel_case)


def datetime_to_epoch(dt):
    """
    Convert a datetime to an unix epoch
    """
    return int((dt - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())


def date_string_to_datetime(date_string):
    """
    Convert a YYYYMMDD date to datetime
    :param date_string: The date in YYYYMMDD format
    :return: a tz naive datetime
    :raise: ValueError when date is incorrect
    """
    if len(date_string) != 8:
        raise ValueError
    return datetime.datetime.strptime(date_string, '%Y%m%d')

