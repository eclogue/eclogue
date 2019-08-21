import time

from bson import ObjectId
# from eclogue.middleware import login_user
from eclogue.model import Model, db


class Job(Model):
    name = 'jobs'

