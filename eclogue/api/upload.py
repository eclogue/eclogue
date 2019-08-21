import time
import pprint

from flask import request, jsonify
from eclogue.model import db
from eclogue.utils import is_edit
from eclogue.lib.helper import get_meta


def upload_file():
    files = request.files
    form = request.form

    return jsonify({
        'message': 'ok',
        'code': 0,
    })
