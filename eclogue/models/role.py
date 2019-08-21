import time

from bson import ObjectId
from eclogue.model import Model


class Role(Model):
    name = 'roles'

    ROLES = ['admin', 'leader', 'member', 'guest']

    def add(self, name, role, parent=None):
        """
        add role record

        :param name: role name
        :param role: play as
        :param parent: parent
        :return:
        """
        if not name or role not in self.ROLES:
            return False

        record = self.collection.find_one({'name': name})
        if not record:
            return False

        parent_record = self.collection.find_one({
            '_id': ObjectId(parent)
        })

        if not parent_record:
            return False

        data = {
            'name': name,
            'role': role,
            'created_at': time.time()
        }

        result = self.collection.insert_one(data)

        return result.inserted_id

