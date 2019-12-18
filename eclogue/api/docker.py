import docker
from flask import request, jsonify


def test_docker():
    client = docker.from_env()
    container = client.containers.create('alpine')
    bits, stat = container.get_archive('/bin')
    f = open('./sh_bin.tar', 'wb')
    for chunk in bits:
        f.write(chunk)
    f.close()

    return jsonify({
        'message': 'ok',
        'code': 0,
        # 'data': result,
    })
