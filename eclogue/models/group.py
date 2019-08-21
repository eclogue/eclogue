from bson import ObjectId
from eclogue.model import Model, db


class Group(Model):

    name = 'groups'

    def __init__(self, name='groups'):
        super(Group, self).__init__(name)
