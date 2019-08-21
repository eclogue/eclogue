import hashlib
import json
import yaml
import os
import zipfile
import tarfile
import random

from eclogue.model import db
from eclogue.config import config


def collection_array(cursor):
    data = []
    for item in cursor:
        data.append(item)
    return data


def md5(content):
    content = content.encode('utf8')
    return hashlib.md5(content).hexdigest()


def parse_task(content=''):
    data = try_json(content)
    if not data:
        data = yaml.load(content)
    if not data:
        return False

    return data


def try_json(string):
    try:
        return json.loads(string)
    except ValueError:
        return False


def file_md5(filename):
    def file_as_bytes(file):
        with file:
            return file.read()
    return hashlib.md5(file_as_bytes(open(filename, 'rb'))).hexdigest()


def check_workspace(path=None, child=None):
    workspace = config.workspace['playbook']
    if not os.path.exists(workspace):
        return True

    if not path:
        path = workspace
    #     filename = workspace
    # else:

    filename = path
    if child:
        filename += '/' + child

    index = filename.replace(workspace, '')
    if not index:
        index = '/'

    if os.path.isfile(filename):
        record = db.collection('playbook').find_one({'path': index})
        if not record:
            os.remove(filename)
        return True;
    files = os.listdir(filename)
    for file in files:  # 遍历文件夹
        check_workspace(filename, file)
    return True


def is_edit(file):
    """
    @todo large than 15MB make as can't edit
    :param file:
    :return:
    """
    if not file:
        return False
    if hasattr(file, 'read'):
        demo = file.read(1024)
        file.seek(0)
    else:
        fd = open(file, 'rb')
        demo = fd.read(1024)
        fd.close()

    textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
    is_binary = lambda bytes: bool(bytes.translate(None, textchars))
    return not is_binary(demo)


def make_zip(source_dir, output):
    zipf = zipfile.ZipFile(output, 'w')
    pre_len = len(os.path.dirname(source_dir))
    for parent, dirnames, filenames in os.walk(source_dir):
        for filename in filenames:
            pathfile = os.path.join(parent, filename)
            arcname = pathfile[pre_len:].strip(os.path.sep)     #相对路径
            zipf.write(pathfile, arcname)
    zipf.close()


def gen_password():
    rand_str = '1234567890abcdefghijklmnopqrstuvwxyz!@#$%^&*()'
    return str(random.sample(rand_str, 8))


def extract(filename, target):
    print('extract file::', filename, target)
    if filename.endswith('.zip'):
        with zipfile.ZipFile(filename) as zf:
            zf.extractall(target)
    elif filename.find('.tar') > -1:
        with tarfile.open(filename) as tar:
            tar.extractall(target)


def mkdir(path, mode=0o700):
    if not path or os.path.exists(path):
        return []

    (head, tail) = os.path.split(path)
    res = mkdir(head, mode)
    os.mkdir(path)
    os.chmod(path, mode)
    res += [path]

    return res
