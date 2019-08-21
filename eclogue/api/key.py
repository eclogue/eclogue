from flask import request, jsonify, current_app
from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from io import StringIO
import hashlib
import time


@jwt_required
def add_key():
    user = login_user
    files = request.files
    form = request.form
    print(form, files)
    if 'file' not in files or not form.get('name') or not form.get('password'):
        return jsonify({
            'message': 'illegal param',
            'code': 104000
        }), 400

    password = form.get('password')
    secret = get_secret(password)
    name = form.get('name')
    comment = form.get('comment', '')
    file = files['file']
    fer = Fernet(secret)
    content = StringIO(fer.encrypt(file.read()))
    filename = secure_filename(file.filename)
    insert_id = db.save_file(filename, content)
    private_key = {
        'file_id': insert_id,
        'username': user['username'],
        'filename': name,
        'comment': comment,
        'created_at': int(time.time())
    }

    db.collection('private_keys').insert_one(private_key)
    db.get_file(insert_id)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def get_secret(password):
    salt = current_app.config.file_secret
    length = len(password)
    prefix = salt[:length]
    postfix = salt[length:]
    secret = prefix + password + postfix

    return hashlib.sha256(secret).hexdigest()
