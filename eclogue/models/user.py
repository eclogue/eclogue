from bson import ObjectId
from eclogue.model import Model, db
from eclogue.models.team import Team
from eclogue.models.role import Role
from eclogue.models.menu import Menu
from eclogue.models.group import Group
from eclogue.models.host import Host


class User(Model):
    name = 'users'

    def get_permissions(self, user_id):
        """
        get user permissions
        :param user_id: user id
        :return: list
        """
        user = self.find_by_id(user_id)
        if not user:
            return []

        team = Team()
        relate_team = db.collection('team_users').find({'user_id': user_id})
        team_ids = list(map(lambda i: i['_id'], relate_team))
        role_ids = []
        menus = []
        if team_ids:
            team_records = team.find_by_ids(team_ids)
            for record in team_records:
                team_role = db.collection('roles').find_one({
                    'name': record.get('name'),
                    'type': 'team',
                })
                if not team_role:
                    continue

                role_ids.append(team_role.get('_id'))

        print('role ids', role_ids)
        roles = db.collection('user_roles').find({'user_id': user_id})
        roles = list(roles)
        print('roles', roles)

        if roles:
            ids = map(lambda i: i['role_id'], roles)
            role_ids += list(ids)

        if role_ids:
            where = {
                'role_id': {
                    '$in': role_ids
                }
            }
            records = db.collection('role_menus').find(where).sort('id', 1)
            # records = list(records)
            # ids = list(map(lambda i: i['m_id'], records))
            menu = Menu()
            for record in records:
                item = menu.find_by_id(record['m_id'])
                print('mpid', item.get('mpid'))
                if not item or item.get('mpid') == '-1':
                    continue

                item['actions'] = record.get('actions', ['get'])
                menus.append(item)
            # menus = Menu().find_by_ids(ids)

        roles = Role().find_by_ids(role_ids)

        return menus, roles

    def get_hosts(self, user_id):
        where = {
            'user_id': user_id,
        }
        relations = db.collection('user_hosts').find(where)
        group_ids = []
        host_ids = []
        for item in relations:
            if item.get('type') == 'group':
                group_ids.append(item.get('group_id'))
            else:
                host_ids.append(item.get('host_id'))
        data = {}
        if group_ids:
            groups = Group().find_by_ids(group_ids)
            data['groups'] = groups

        if host_ids:
            hosts = Host().find_by_ids(host_ids)
            data['hosts'] = hosts

        return data
