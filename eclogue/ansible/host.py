import os
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.data import InventoryData
from ansible.plugins.inventory.ini import InventoryModule
from ansible.parsing.dataloader import DataLoader
from eclogue.ansible.inventory import HostsManager


def parser_inventory(sources, to_dict=False):
    if isinstance(sources, HostsManager):
        manager = sources
    else:
        loader = DataLoader()
        manager = HostsManager(loader=loader, sources=sources)
    groups = manager.groups
    data = {}
    for name, group in groups.items():
        if name == 'all':
            continue
        hosts = group.get_hosts()
        for host in hosts:
            host_info = host.serialize()
            groups = host_info['groups']
            # node name same as group name
            if not host_info.get('vars'):
                for item in groups:
                    if not item or not item.get('vars'):
                        continue
                    host_info = item
                    break
            print('?????~~~~~~~~~~~=====', host_info)

            data[name] = host_info
    return dict_inventory(data) if to_dict else data


def dict_inventory(inventory):
    bucket = dict()
    for key, groups in inventory.items():
        for value in groups:
            group_name = os.path.basename(key)
            inventory_vars = value.get('vars', {})
            field = os.path.basename(value.get('name'))
            hosts = {
                field: {
                    'ansible_ssh_host': inventory_vars.get('ansible_ssh_host', value.get('address')),
                    'ansible_ssh_user': inventory_vars.get('ansible_ssh_user', 'root'),
                    'ansible_ssh_port': inventory_vars.get('ansible_ssh_port', 22)
                }
            }

            if bucket.get(group_name):
                bucket[group_name]['hosts'].update(hosts)
            else:
                bucket[group_name] = {
                    'hosts': hosts
                }
    print('++++++++++++++++=====', bucket)
    return bucket
