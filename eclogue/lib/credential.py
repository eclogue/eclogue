from bson import ObjectId
from eclogue.ansible.vault import Vault
from eclogue.config import config
from eclogue.model import db


def encrypt_credential(text):
    secret = config.vault.get('secret')
    options = {
        'vault_pass': secret
    }
    vault = Vault(options=options)

    return vault.encrypt_string(text)


def decrypt_credential(text):
    secret = config.vault.get('secret')
    options = {
        'vault_pass': secret
    }
    vault = Vault(options=options)

    return vault.decrypt_string(text)


def get_credential_content_by_id(_id, field):
    if not isinstance(_id, ObjectId):
        _id = ObjectId(_id)

    record = db.collection('credentials').find_one({'_id': _id})
    if not record or not record.get('body'):
        return False

    body = record.get('body')
    if not body.get(field):
        return False

    return decrypt_credential(body.get(field))
