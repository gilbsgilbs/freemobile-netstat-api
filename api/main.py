from flask import Flask
from flask.ext.restful import Api

from api.routes import Routing

app = Flask('fmns-api')
api = Api(app)
routes = Routing(api)


def run(*args, **kwargs):
    app.run(*args, **kwargs)
