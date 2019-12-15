from flask import Blueprint

# Blueprint constructor (args: blueprint name, module where the blueprint is located)
main = Blueprint('main', __name__)

from . import views, errors
