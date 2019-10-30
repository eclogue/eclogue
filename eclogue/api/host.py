import yaml
import pprint
from flask import request, jsonify
from eclogue.middleware import jwt_required, login_user
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.data import InventoryData
from ansible.inventory.manager import InventoryManager
from ansible.plugins.inventory.ini import InventoryModule
from ansible.parsing.dataloader import DataLoader
from eclogue.model import db
from eclogue.ansible.inventory import HostsManager
from eclogue.config import config
from eclogue.ansible.loader import YamlLoader


def dump_inventory():
    hosts = db.collection('playbook').find_one({'role': 'hosts', 'is_edit': True})
    loader = DataLoader()
    root = config.app_root
    filename = root + '/playbook/hosts.yaml'
    loader = YamlLoader()
    pprint.pprint(yaml.load(hosts['content']))
    inventory = HostsManager(loader=loader, sources=hosts['content'])
    pprint.pprint(inventory.get_hosts())
    return jsonify({
        'message': 'ok',
    })


def parser_inventory(sources):
    loader = DataLoader()
    inventory = InventoryData()
    parser = InventoryModule()
    manager = HostsManager(loader=loader, sources=sources)
    groups = manager.groups
    for group in groups:
        hosts = group.get_hosts()
        for host in hosts:
            print('~~~~~~~~~~~~~~~~~', host.serialize(), '=======', host.get_vars())
