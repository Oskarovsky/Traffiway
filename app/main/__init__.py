from flask import Blueprint

# Blueprint constructor (args: blueprint name, module where the blueprint is located)
main = Blueprint('main', __name__)

from . import views, errors
from ..models import Permission


@main.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)
