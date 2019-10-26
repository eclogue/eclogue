import time

from bson import ObjectId
# from eclogue.middleware import login_user
from eclogue.model import Model, db
from eclogue.models.role import Role


class Team(Model):
    name = 'teams'

    def add_member(self, team_id, members, owner_id):
        team = self.find_by_id(team_id)
        if not team or owner_id not in team.get('master'):
            return False

        current_user = db.collection('users').find_one({'_id': ObjectId(owner_id)})
        for user_id in members:
            where = {
                'user_id': user_id,
            }

            data = where.copy()
            data['team_id'] = team_id
            data['created_at'] = time.time()
            data['add_by'] = current_user.get('username')
            db.collection('team_members').update_one(where, {'$set': data}, upsert=True)

    def get_roles(self, team_id):
        team_roles = self.db.collection('team_roles').find({'team_id': team_id})
        team_roles = list(team_roles)
        if not team_roles:
            return team_roles

        role_ids = map(lambda i: i['role_id'], team_roles)
        role_ids = list(role_ids)

        return Role.find_by_ids(role_ids)
