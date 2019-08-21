import re
import os
from bson import ObjectId
from eclogue.ansible.loader import YamlLoader
from eclogue.ansible.inventory import HostsManager
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.models.host import host_model
from eclogue.models.group import Group


@jwt_required
def get_inventory_from_cmdb():
    is_admin = login_user.get('is_admin')
    user_id = login_user.get('user_id')
    tree = []
    if not is_admin:
        tree = host_model.get_host_tree(user_id)

        return tree

    condition = [
        {
            '$unwind': '$group'},
        {
            '$group': {
                '_id': '$group',
                'machines': {
                    '$push': '$_id'
                }
            }
        }
    ]

    result = db.collection('machines').aggregate(condition)
    for item in result:
        group_id = item.get('_id')
        if group_id == 'ungrouped':
            group_name = group_id
            data = {
                '_id': group_id,
                'key': group_id,
                'title': group_id,
                'value': '@'.join(['group', group_id, group_id]),
                'count': len(item.get('machines')),
                'children': [],
            }
            hosts = host_model.collection.find({
                'group': {
                    '$in': [group_id]
                }
            })
        else:
            group_info = Group().find_by_id(group_id)
            if not group_info:
                continue
            group_name = group_info.get('name')
            data = {
                '_id': group_id,
                'key': group_id,
                'title': group_info.get('name'),
                'value': '@'.join(['group', str(group_info['_id']), group_info.get('name')]),
                'count': len(item.get('machines')),
                'children': [],
            }
            host_ids = item.get('machines')
            hosts = host_model.find_by_ids(host_ids)

        children = []
        for host in hosts:
            node = {
                '_id': host['_id'],
                'key':  host['_id'],
                'title': host.get('hostname'),
                'value': '@'.join(['node', str(host['_id']),  host.get('hostname')]),
            }
            children.append(node)

        data['children'] = children
        tree.append(data)

    return tree
    # where = {}
    # where2 = {}
    # if keyword:
    #     where = {
    #         'name': {'$regex': keyword}
    #     }
    #     where2 = {
    #         'node_name': {'$regex': keyword}
    #     }
    # records = db.collection('groups').find(where, limit=5)
    # records = list(records)
    # hosts = []
    # for record in records:
    #     region = db.collection('regions').find_one({
    #         '_id': ObjectId(record.get('region'))
    #     })
    #     if not region:
    #         continue
    #     item = {
    #         '_id': record['_id'],
    #         'collection': 'group',
    #         'name':  record.get('name'),
    #         'group': record.get('region'),
    #         'group_name': region.get('name'),
    #         'parent': 'region'
    #     }
    #     hosts.append(item)
    # records = db.collection('machines').find(where2, limit=5)
    # for record in list(records):
    #     if not record.get('group'):
    #         continue
    #
    #     group = db.collection('groups').find_one({
    #         '_id': {
    #             '$in': record.get('group')
    #         }
    #     })
    #     print(group)
    #     if not group:
    #         continue
    #     item = {
    #         '_id': record['_id'],
    #         'collection': 'node',
    #         'name': record.get('node_name'),
    #         'group': record.get('group'),
    #         'group_name': group.get('name'),
    #         'parent': 'group'
    #     }
    #     hosts.append(item)
    # return hosts


def get_inventory_by_book(book_id, keyword=None, book_name='default'):
    condition = {
        'book_id': str(book_id),
        'role': 'hosts',
        'is_edit': True
    }
    cursor = db.collection('playbook').find(condition)
    records = list(cursor)
    hosts = []
    for item in records:
        loader = YamlLoader()
        inventory = HostsManager(loader=loader, sources=item['content'])
        groups = inventory.get_groups_dict()
        index = 0
        for group, names in groups.items():
            index += 1
            group = os.path.basename(group)
            if not names:
                continue

            if keyword:
                pattern = re.compile(keyword, 'i')
                res = pattern.search(group)
                if res is None:
                    continue

            data = {
                '_id': item.get('_id'),
                'name': group,
                'group_name': book_name,
                'collection': 'group',
                'parent': 'entry',
                'key': index,
                'title': group,
                'value': '@'.join(['group', str(item.get('_id')), group]),
            }
            children = []
            for name in names:
                index += 1
                if keyword:
                    pattern = re.compile(keyword, 'i')
                    res = pattern.search(name)
                    if res is None:
                        continue

                value = '@'.join(['node', str(item.get('_id')), name])
                node = {
                    '_id': item['_id'],
                    'name': name,
                    'collection': 'node',
                    'group_name': group,
                    'parent': 'group',
                    'key': index,
                    'title': name,
                    'value': value,
                }
                children.append(node)
            data['children'] = children
            hosts.append(data)
        for group, names in groups.items():
            group = os.path.basename(group)
            if group == 'all':
                continue
            for name in names:
                if keyword:
                    pattern = re.compile(keyword, 'i')
                    res = pattern.search(name)
                    if res is None:
                        continue

                value = '@'.join(['node', str(item.get('_id')), name])
                data = {
                    '_id': item['_id'],
                    'name': name,
                    'collection': 'node',
                    'group_name': group,
                    'parent': 'group',
                    'key': value,
                    'title': name,
                    'value': value,
                }
                hosts.append(data)
    return hosts
