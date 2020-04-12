from bson import ObjectId
from eclogue.model import Model, db


class Group(Model):
    name = 'groups'
