from bson import ObjectId
from eclogue.model import Model, db


class Host(Model):

    name = 'machines'

    def get_host_tree(self, user_id, skip=0, limit=100):
        condition = [
            {
                '$match': {
                    'user_id': user_id,
                }
            },
            {
                '$group': {
                    '_id': '$group_id',
                    'count': {
                        '$sum': 1
                    }
                },
            },
            {
                '$limit': limit,
            },
            {
                '$skip': skip,
            }
        ]
        result = db.collection('user_hosts').aggregate(condition)
        bucket = []

        def load_children(nodes):
            data = []
            for node in nodes:
                data.append({
                    '_id': node.get('_id'),
                    'title': node.get('hostname'),
                    'key': node.get('_id'),
                    'type': 'node',
                })

            return data

        for item in result:
            if item.get('group_id') == 'ungrouped':
                name = item.get('group_id')
                children = db.collection('user_hosts').find({
                    'user_id': user_id,
                    'group_id': name,
                })
                hids = map(lambda i: ObjectId(i.get('host_id')), children)
                hosts = Host().find_by_ids(list(hids))
                children = load_children(hosts)
                bucket.append({
                    '_id': name,
                    'name': name,
                    'title': name,
                    'key': name,
                    'count': item.get('count'),
                    'children': list(children)
                })
            else:
                group_record = db.collection('groups').find_one({'_id': ObjectId(item.get('_id'))})
                if not group_record:
                    # db.collection('user_hosts').delete_one({'_id': item['_id']})
                    continue
                records = db.collection('user_hosts').find({
                    'user_id': user_id,
                    'group_id': item.get('_id'),
                })
                children = []
                for record in records:
                    if record.get('type') == 'node':
                        current = self.get_child(record.get('host_id'))
                        children.append(current)
                    else:
                        hosts = self.collection.find({
                            'group': {
                                '$in': [record.get('group_id')]
                            }
                        })
                        hosts = load_children(hosts)
                        children.extend(list(hosts))
                bucket.append({
                    '_id': group_record['_id'],
                    'title': group_record.get('name'),
                    'count': item.get('count'),
                    'key': group_record['_id'],
                    'children': children,
                })

        return bucket

    def get_child(self, _id):
            host = self.find_by_id(_id)
            return {
                '_id': _id,
                'title': host.get('hostname'),
                'key': _id,
                'type': 'node',
            }
