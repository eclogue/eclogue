
from flask import request, jsonify
from eclogue.gitlab.api import GitlabApi


def test_gitlab():
    gl = GitlabApi()
    result = gl.dowload_artifact()
    print(result)
    return jsonify({
        'message': 'ok',
        'data': str(result),
    })
