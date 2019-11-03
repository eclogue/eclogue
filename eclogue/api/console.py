from tempfile import NamedTemporaryFile
from flask import request, jsonify
from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from eclogue.ansible.runer import AdHocRunner, PlayBookRunner
from eclogue.config import config
from eclogue.lib.helper import parse_cmdb_inventory
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.lib.logger import logger


@jwt_required
def run_task():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 114000,
        }), 400

    run_type = payload.get('type')
    inventory = payload.get('inventory')
    private_key = payload.get('private_key')
    module = payload.get('module')
    args = payload.get('args')
    entry = payload.get('entry')
    become_mehtod = payload.get('become_method')
    become_user = payload.get('become_user')
    verbosity = payload.get('verbosity', 0) or 1
    extra_options = payload.get('extraOptions')
    hosts = parse_cmdb_inventory(inventory)
    if not hosts:
        return jsonify({
            'message': 'invalid inventory',
            'code': 114001,
        }), 400

    options = {}
    if extra_options:
        options.update(extra_options)

    if verbosity:
        options['verbosity'] = verbosity

    if become_mehtod:
        options['become'] = 'yes'
        options['become_method'] = become_mehtod
        if become_user:
            options['become_user'] = become_user

    if run_type == 'adhoc':
        if not module:
            return jsonify({
                'message': 'invalid module',
                'code': 114002,
            }), 400
        tasks = [{
            'action': {
                'module': module,
                'args': args
            }
        }]

        with NamedTemporaryFile('w+t', delete=True) as fd:
            if private_key:
                key_text = get_credential_content_by_id(private_key, 'private_key')
                if not key_text:
                    return jsonify({
                        'message': 'invalid private_key',
                        'code': 104033,
                    }), 401
                fd.write(key_text)
                fd.seek(0)
                options['private_key'] = fd.name

            runner = AdHocRunner(hosts, options=options)
            logger.info('run ansible-adhoc', extra={'hosts': hosts, 'options': options})
            runner.run('all', tasks)
            result = runner.get_result()

            return jsonify({
                'message': 'ok',
                'code': 0,
                'data': result
            })
    else:
        if not entry:
            return jsonify({
                'message': 'invalid entry',
                'code': 114004,
            }), 400

        with NamedTemporaryFile('w+t', delete=True) as fd:
            key_text = get_credential_content_by_id(private_key, 'private_key')
            if not key_text:
                return jsonify({
                    'message': 'invalid private_key',
                    'code': 104033,
                }), 401
            fd.write(key_text)
            fd.seek(0)
            options['private_key'] = fd.name
            with NamedTemporaryFile('w+t', delete=True) as fh:
                fh.write(entry)
                fh.seek(0)
                runner = PlayBookRunner(hosts, options)
                logger.info('run ansible-playbook', extra={'hosts': hosts, 'options': options})
                runner.run(fh.name)
                result = runner.get_result()

                return jsonify({
                    'message': 'ok',
                    'code': 0,
                    'data': result
                })

