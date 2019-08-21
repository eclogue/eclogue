import time

from bson import ObjectId
from eclogue.model import Model


class TeamUser(Model):
    name = 'team_members'

