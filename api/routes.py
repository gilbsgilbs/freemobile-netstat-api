from api import resources


class Routing(object):
    def __init__(self, api):
        api.add_resource(resources.InfoService, '/')
        api.add_resource(resources.Device, '/device/<string:device_id>')
        api.add_resource(resources.DeviceStat, '/device/<string:device_id>/daily/<string:date>')
        api.add_resource(resources.NetworkUsageChart, '/chart/network-usage')
