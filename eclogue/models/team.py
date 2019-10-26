import time

from bson import ObjectId
# from eclogue.middleware import login_user
from eclogue.model import Model, db


class Team(Model):
    name = 'teams'

    def add_member(self, data, current_user=None):
        team = self.find_by_id(data.get('team_id'))
        if not team:
            return False

        where = {
            'team_id': data.get('team_id'),
            'user_id': data.get('user_id'),
            'is_owner': data.get('is_owner'),
        }

        data = where.copy()
        data['created_at'] = time.time()
        data['add_by'] = current_user
        db.collection('team_members').update_one(where, {'$set': data}, upsert=True)

