import os
import json
import time
import configparser
import yaml
import re

from eclogue.model import db
from bson import ObjectId
from jinja2 import Template
from eclogue.ansible.host import parser_inventory
from eclogue.ansible.vault import Vault
from eclogue.config import config
from eclogue.lib.integration import Integration
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.models.application import Application
from eclogue.models.playbook import Playbook
from eclogue.models.book import Book
from eclogue.models.group import Group
from eclogue.models.host import Host
from eclogue.models.credential import Credential


def ini_yaml(text):
    config = configparser.RawConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read_string(text)
    inventory = {}
    varRegex = re.compile("[\t ]*([a-zA-Z][a-zA-Z0-9_]+)=('[^']+'|\"[^\"]+\"|[^ ]+)")
    noQuotesNeededRegex = re.compile("^([-.0-9a-zA-Z]+|'[^']+'|\"[^\"]+\")$")
    # Parse host variable and return corresponding YAML object
    def parse_value(value):
        # Integers, booleans and quoted strings strings must not be quoted
        if noQuotesNeededRegex.match(value):
            result = yaml.load('value: ' + value)['value']
        else:
            result = yaml.load('value: "' + value + '"')['value']
        if isinstance(result, str):
            if '\\n' in result:  # Use YAML block literal for multi-line strings
                return result.replace('\\n', '\n')
            else:
                try:  # Unwrap nested YAML structures
                    new_result = yaml.load('value: ' + result)['value']
                    if isinstance(new_result, list) or isinstance(new_result, dict):
                        result = new_result
                except:
                    pass

        return result

    for section in config.sections():
        group = section.split(':')
        if len(group) == 1:  # section contains host group
            for name, value in config.items(section):
                if value:
                    value = name + '=' + value
                else:
                    value = name
                host = re.split(' |\t', value, 1)
                hostname = host[0]
                hostvars = host[1] if len(host) > 1 else ''
                hostvars = varRegex.findall(hostvars)
                inventory.setdefault('all', {})\
                    .setdefault('children', {})\
                    .setdefault(group[0], {})\
                    .setdefault('hosts', {})[hostname] = {}
                for hostvar in hostvars:
                    value = parse_value(hostvar[1])
                    inventory.setdefault('all', {})\
                        .setdefault('children', {})\
                        .setdefault(group[0], {})\
                        .setdefault('hosts', {})[hostname][hostvar[0]] = value
        elif group[1] == 'vars':  # section contains group vars
            for name, value in config.items(section):
                value = parse_value(value)
                inventory.setdefault('all', {})\
                    .setdefault('children', {})\
                    .setdefault(group[0], {})\
                    .setdefault('vars', {})[name] = value
        elif group[1] == 'children':  # section contains group of groups
            for name, value in config.items(section):
                inventory.setdefault('all', {})\
                    .setdefault('children', {})\
                    .setdefault(group[0], {})\
                    .setdefault('children', {})[name] = {}

    return inventory


def load_ansible_playbook(payload):
    template = payload.get('template')
    extra = payload.get('extra', {}) or {}
    if not template:
        return {
            'message': 'invalid params',
            'code': 104000,
        }

    name = template.get('name')
    if not name:
        return {
            'message': 'name required',
            'code': 104000,
        }

    entry = template.get('entry')
    if len(entry) < 2:
        return {
            'message': 'entry not found',
            'code': 104001,
        }

    book_id, entry_id = entry
    book_record = Book.find_by_id(book_id)
    if not book_record:
        return {
            'message': 'book not found',
            'code': 1040011,
        }

    entry_record = Playbook.find_by_id(entry_id)
    if not entry_record:
        return {
            'message': 'entry not found',
            'code': 104001,
        }

    inventory_type = template.get('inventory_type', 'file')
    inventory = template.get('inventory', None)
    if not inventory:
        return {
            'message': 'invalid param inventory',
            'code': 104002
        }

    if inventory_type == 'file':
        inventory_record = parse_file_inventory(inventory)
    else:
        inventory_record = parse_cmdb_inventory(inventory)

    if not inventory_record:
        return {
            'message': 'illegal inventory',
            'code': 104002
        }

    group_name = inventory_record.keys()
    if not inventory_record:
        return {
            'message': 'invalid param inventory',
            'code': 104002
        }

    roles = template.get('roles')
    role_names = []
    if roles:
        roles = list(map(lambda i: ObjectId(i), roles))
        check = Playbook.find({
            'book_id': book_id,
            '_id': {
                '$in': roles,
            }
        })
        check = list(check)
        if not check:
            return {
                'message': 'invalid param role',
                'code': 104003
            }

        role_names = list(map(lambda i: i.get('name'), check))

    extra_vars = {
        'node': list(group_name),
    }

    private_key = template.get('private_key')
    if private_key:
        key_record = Credential.find_one({'_id': ObjectId(private_key), 'type': 'private_key'})
        if not key_record:
            return {
                'message': 'invalid private key',
                'code': 104031
            }

    variables = extra.get('extraVars') or {}
    # variables.update({'node': inventory_record.get('limit')})
    if type(variables) in [dict, list]:
        variables = yaml.safe_dump(variables)

    app = template.get('app')
    if app:
        # @todo status=1
        app_record = Application.find_by_id(app)
        if not app_record:
            return {
                'message': 'invalid app',
                'code': 104043
            }

        app_type = app_record.get('type')
        app_params = app_record.get('params')
        integration = Integration(app_type, app_params)
        check_app = integration.check_app_params()
        if not check_app:
            return {
                'message': 'invalid app',
                'code': 104014
            }

        job_space = integration.get_job_space(name)
        if job_space and variables:
            tpl = Template(variables)
            variables = tpl.render(ECLOGUE_JOB_SPACE=job_space)

    if variables:
        variables = yaml.safe_load(variables)
        variables and extra_vars.update(variables)

    options = dict()
    extra_options = template.get('extraOptions')
    if extra_options and type(extra_options) == dict:
        options = extra_options.copy()
        # default_options = get_default_options('playbook')
        # for key, value in extra_options.items():
        #     if default_options.get(key):
        #         options[key] = value

    options['skip_tags'] = template.get('skip_tags', [])
    options['inventory'] = inventory_record
    # @todo limit
    # options['limit'] = inventory_record.get('limit', None)
    # options['credential'] = template.get('credential')
    options['limit'] = template.get('limit', 'all')
    options['forks'] = template.get('forks', 5)
    options['tags'] = template.get('tags', [])
    options['listtags'] = template.get('listtags', False)
    options['listtasks'] = template.get('listtasks', False)
    options['timeout'] = template.get('timeout', 10)
    options['verbosity'] = template.get('verbosity', 0)
    become_method = template.get('become_method')
    if become_method:
        options['become'] = 'yes'
        options['become_method'] = become_method
        if template.get('become_user'):
            options['become_user'] = template.get('become_user')

    vault_pass = template.get('vault_pass')
    if vault_pass:
        vault_record = Credential.find_one({'_id': ObjectId(vault_pass)})
        if not vault_record or not vault_record.get('body'):
            return {
                'message': 'invalid vault pass',
                'code':  104004
            }

        vault_body = vault_record.get('body')
        vault = Vault({
            'vault_pass': config.vault.get('secret')
        })
        options['vault_pass'] = vault.decrypt_string(vault_body.get('vault_pass'))

    options['verbosity'] = template.get('verbosity', 0)
    options['diff'] = template.get('diff', False)
    # options['vault'] = template.get('vault')
    options['extra_vars'] = json.dumps(extra_vars)
    status = int(extra.get('status', 0))

    return {
        'message': 'ok',
        'data': {
            'inventory': options['inventory'],
            'options': options,
            'name': name,
            'entry': entry_record['name'],
            'book_id': book_id,
            'book_name': book_record['name'],
            'roles': role_names,
            'inventory_type': inventory_type,
            'private_key': private_key,
            'template': template,
            'extra': extra,
            'status': status,
        }
    }


def load_ansible_adhoc(payload):
    template = payload.get('template')
    extra = payload.get('extra')
    module = template.get('module')
    args = template.get('args')
    inventory = template.get('inventory')
    private_key = template.get('private_key')
    verbosity = template.get('verbosity')
    become_method = template.get('become_method')
    become_user = template.get('become_user')
    extra_options = template.get('extraOptions')
    name = template.get('name')
    schedule = extra.get('schedule')

    if not module or not inventory:
        return {
            'message': 'miss required params',
            'code': 104002,
        }

    # check_module = db.collection('ansible_modules').find_one({
    #     'name': module
    # })
    #
    # if not check_module:
    #     return {
    #         'message': 'invalid module',
    #         'code': 104003,
    #     }

    inventory = parse_cmdb_inventory(inventory)
    if not inventory:
        return {
            'message': 'invalid inventory',
            'code': 104004,
        }

    key_text = get_credential_content_by_id(private_key, 'private_key')
    if not key_text:
        return {
            'message': 'invalid private key',
            'code': 104004,
        }

    options = {
        'verbosity': verbosity,
        'check': False,
        'hosts': inventory,
    }
    if become_method:
        options['become'] = 'yes'
        options['become_method'] = become_method
        if become_user:
            options['become_user'] = become_user

    if extra_options:
        options.update(extra_options)

    return {
        'message': 'ok',
        'data': {
            'inventory': inventory,
            'options': options,
            'name': name,
            'module': module,
            'args': args,
            'private_key': private_key,
            'template': payload,
            'schedule': schedule,
            'extra': extra,
        }
    }


def _load_extra_vars(data):
    extra_vars = []
    for key, value in data.items():
        extra_vars.append(key + '=' + str(value).replace('\'', '"'))

    return ' '.join(extra_vars)


def load_inventory(content, group='all'):
    # content = yaml.safe_load(content)
    # if not content:
    #     raise yaml.YAMLError('parse inventory error')
    content = parser_inventory(content, True)
    inventory = dict()
    if group == 'all':
        inventory['all'] = dict()
        ungrouped = dict()
        for key, value in content.items():
            if not value.get('hosts'):
                continue
            ungrouped.update(value.get('hosts'))
        inventory['all']['hosts'] = ungrouped
        return json.dumps(inventory)
    if not content.get('group'):
        raise ValueError('inventory group: ' + group + ' not found')
    inventory[group] = content.get('group')
    return json.dumps(inventory)


def process_ansible_setup(result):
    """
    :param result: dict
    :return: dict
    """
    success = result.get('success')
    if not success:
        return False

    records = []
    for host, info in success.items():
        facts = info['ansible_facts']
        processor = {
            'architecture': facts.get('ansible_processor'),
            'cores': facts.get('ansible_processor_cores'),
            'vscups': facts.get('ansible_processor_vcpus'),
        }
        record = {
            'ansible_hostname': host,
            'memory': facts['ansible_memtotal_mb'],
            'processor': processor,
            'ipv6': facts.get('ansible_default_ipv6'),
            'ipv4': facts.get('ansible_default_ipv4'),
            'kernel': facts.get('ansible_kernel'),
            'node_name': facts.get('ansible_nodename'),
            'swap': facts.get('ansible_swaptotal_mb'),
            'bios_version': facts.get('ansible_bios_version'),
            'all_ipv4_addresses': facts.get('ansible_all_ipv4_addresses'),
            'all_ipv6_addresses': facts.get('ansible_all_ipv6_addresses'),
            'apparmor': facts.get('ansible_apparmor'),
            'architecture': facts.get('ansible_architecture'),
            'domain': facts.get('ansible_domain'),
            'disk': facts.get('ansible_mounts'),
            'system': facts.get('ansible_system'),
            'dns': facts.get('ansible_dns'),
            'product_name': facts.get('ansible_product_name'),
            'hostname': facts.get('ansible_hostname'),
            'lsb': facts.get('ansible_lsb'),
            'interfaces': facts.get('ansible_interfaces'),
            'os_family': facts.get('ansible_os_family'),
            'created_at': int(time.time()),
        }
        records.append(record)

    return records


def parse_file_inventory(inventory_params):
    data = {}
    if type(inventory_params) != list:
        inventory_params = [inventory_params]

    for inventory_str in inventory_params:
        inventory_list = inventory_str.split('@')
        if len(inventory_list) is not 3:
            return False

        mark_name, _id, group = inventory_list
        record = Playbook.find_one({'_id': ObjectId(_id)})
        if not record:
            return False

        node = parser_inventory(record['content'], True)
        # @todo make same as cmdb
        # record['content'] = json.dumps(record['content'])
        # record['limit'] = group
        data.update(node)

    return data


def parse_cmdb_inventory(inventory):
    if type(inventory) != list:
        inventory = [inventory]

    hosts = {}
    data = {}
    for inventory_str in inventory:
        inventory_list = inventory_str.split('@')
        if len(inventory_list) is not 3:
            continue

        collection, _id, group_name = inventory_list
        if collection == 'group':
            if _id == 'ungrouped':
                group = {
                    '_id': _id,
                }
            else:
                group = Group.find_one({'_id': ObjectId(_id)})
                if not group:
                    continue

            records = Host.find({'group': {'$in': [str(group['_id'])]}})
            for record in records:
                hosts[record['hostname']] = {
                    'ansible_ssh_host': record.get('ansible_ssh_host'),
                    'ansible_ssh_user': record.get('ansible_ssh_user', 'root'),
                    'ansible_ssh_port': record.get('ansible_ssh_port', '22'),
                }
        else:
            group_name += '_node'
            record = Host.find_one({'_id': ObjectId(_id)})
            if record:
                hosts[record['node_name']] = {
                    'ansible_ssh_host': record.get('ansible_ssh_host'),
                    'ansible_ssh_user': record.get('ansible_ssh_user', 'root'),
                    'ansible_ssh_port': record.get('ansible_ssh_port', 22),
                }

        if not hosts:
            continue

        data[group_name] = {
            'hosts': hosts
        }

    # inventory = json.dumps(hosts)

    return data


def get_meta(pathname):
    pathname = pathname.rstrip('/')
    home_path, filename = os.path.split(pathname)
    meta = {
        'name': filename
    }
    path_split = pathname.lstrip('/').split('/')
    path_len = len(path_split)
    if path_len is 1:
        filename = path_split[0] or 'root'
        if filename.find('hosts') >= 0:
            meta['role'] = 'hosts'
        elif filename.find('entry') >= 0:
            meta['role'] = 'entry'
        else:
            meta['role'] = path_split[0] or 'unknown'
    elif path_len is 2:
        meta['role'] = filename
    elif path_len >= 3:
        meta['role'] = path_split[2]
        meta['project'] = path_split[1]

    return meta

