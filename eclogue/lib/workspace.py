import os
import time
import re
import pymongo
import yaml
from tempfile import TemporaryDirectory, NamedTemporaryFile
from bson import ObjectId
from eclogue.config import config
from eclogue.model import db
from eclogue.utils import is_edit, file_md5, md5, extract
from eclogue.ansible.vault import Vault
from eclogue.models.book import Book
from eclogue.models.configuration import Configuration
from eclogue.model import Model


class Workspace(object):

    def __init__(self, root_path=None):
        self._base_dir = root_path or config.workspace.get('base_dir', '/var/lib/eclogue')
        self._spaces = {
            'workspace': 0o755,
            'jobs': 0o755,
            'books': 0o755
        }
        self._initialize()
        self.book_dirs = {}

    @property
    def workspace(self):
        return self._base_dir + '/workspace'

    @property
    def book(self):
        return self._base_dir + '/books'

    @property
    def job(self):
        return self._base_dir + '/jobs'

    def _initialize(self):
        if not os.path.exists(self._base_dir):
            os.mkdir(self._base_dir, 0o755)
        os.chdir(self._base_dir)
        for name, mod in self._spaces.items():
            self._check_make(name, mod)

    def get_galaxy_space(self):
        dirname = [self.workspace, 'galaxy', 'roles']
        dirname = '/'.join(dirname)
        if not os.path.exists(dirname):
            self.mkdir(dirname, 0o700)

        return dirname

    def get_vcs_space(self, vcs_type, cache=True):
        cache_dir = '/'.join([self.workspace, 'svc', vcs_type, 'cache'])
        if cache:
            if cache:
                self.mkdir(os.path.dirname(cache_dir), 0o700)

        return cache_dir

    def get_gitlab_artifacts_file(self, job_name, project_id, job_id):
        path = '/'.join([self.job, job_name, 'gitlab', project_id, job_id])
        if not os.path.exists(path):
            self.mkdir(path)
        filename = 'job_id.zip'

        return path + '/' + filename

    def get_galaxy_roles_path(self):
        dirname = [self.workspace, 'galaxy']
        dirname = '/'.join(dirname)

        return dirname

    def setup_book(self, name, roles=None):
        return self.load_book_from_db(name=name, roles=roles)

    def get_workspace(self, name):
        """
        :param name:
        :return:
        """
        return self._check_make(self.workspace + '/' + name)

    def pre_task(self, build_id):
        task_space = self.job + '/' + build_id
        self._check_make(task_space, 0o755)

    def _check_make(self, path, mod=0o755):
        if not os.path.exists(path):
            self.mkdir(path, 0o755)
        return path

    def check_workspace(self, path=None, child=None):
        if not path:
            path = self.workspace
        #     filename = workspace
        # else:
        filename = path
        if child:
            filename += '/' + child
        index = filename.replace(self.workspace, '')
        if not index:
            index = '/'
        if os.path.isfile(filename):
            # can not import playbook model
            record = Model.build_model('playbooks').find_one({'path': index})
            if not record:
                os.remove(filename)
            return True
        files = os.listdir(filename)
        for file in files:  # 遍历文件夹
            self.check_workspace(filename, file)
        return True

    def import_book_from_dir(self, root_path, book_id, exclude=['*.retry'], links=False):
        bucket = []
        cursor = 0
        parent = root_path
        book_record = Book.find_one({'_id': ObjectId(book_id)})
        pattern = '|'.join(exclude).replace('*', '.*?')
        for current, dirs, files in os.walk(root_path, topdown=True, followlinks=links):
            pathname = current.replace(root_path, '') or '/'
            if exclude:
                match = re.search(pattern, pathname)
                if match:
                    continue

            dir_record = {
                'book_id': str(book_record.get('_id')),
                'path': pathname,
                'is_dir': True,
                'is_edit': False,
                'seq_no': cursor,
                'parent': None,
                'created_at': int(time.time()),
            }
            if not current == root_path:
                dir_record['parent'] = parent
                meta = Workspace.get_meta(pathname=pathname)
                dir_record.update(meta)
                dir_record['additions'] = meta

            parent = pathname
            bucket.append(dir_record)
            for file in files:
                pathname = parent.rstrip('/') + '/' + file
                if exclude:
                    match = re.match(pattern, pathname)
                    if match:
                        continue

                cursor += 1
                filename = current + '/' + file
                can_edit = is_edit(filename)
                file_record = dir_record.copy()
                file_record['is_edit'] = can_edit
                file_record['path'] = pathname
                file_record['parent'] = parent
                file_record['is_dir'] = False
                file_record['seq_no'] = cursor
                if is_edit:
                    with open(filename, 'r', encoding='utf-8') as fd:
                        file_record['content'] = fd.read()
                        file_record['md5'] = md5(file_record['content'])
                        file_record['is_encrypt'] = Vault.is_encrypted(file_record['content'])

                meta = self.get_meta(file_record['path'])
                file_record.update(meta)
                file_record['additions'] = meta
                bucket.append(file_record)
            cursor += 1
        is_entry = filter(lambda i: i.get('role') == 'entry', bucket)
        is_entry = list(is_entry)
        if not is_entry:
            path = '/entry.yml'
            entry = {
                'book_id': str(book_record.get('_id')),
                'path': path,
                'is_dir': False,
                'is_edit': True,
                'seq_no': 0,
                'content': '',
                'parent': None,
                'created_at': int(time.time()),
            }
            meta = self._get_role(path)
            entry.update(meta)
            entry['additions'] = meta
            bucket.append(entry)

        return bucket

    def get_book_entry(self, name, entry):
        return '/'.join([self.book, name, entry])

    def get_book_space(self, name):
        dir = self.book + '/' + name
        if not os.path.exists(dir):
            self.mkdir(dir)

        return dir

    def write_book_file(self, book_name, document):
        filename = document.get('path')
        content = document.get('content')
        filename = '/'.join([self.book, book_name, filename.strip('/')])
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            self.mkdir(dirname)

        if not document.get('is_dir'):
            with open(filename, 'w') as fd:
                fd.write(content)

    def load_book_from_db(self, name, roles=None, build_id=False):
        book = Book.find_one({'name': name})
        if not book:
            return False

        files = Model.build_model('playbook').find({'book_id': str(book['_id'])})\
            .sort([('is_edit', pymongo.ASCENDING), ('path', pymongo.ASCENDING)])
        files = list(files)
        if not files:
            return False

        if build_id:
            bookspace = os.path.join(self.book, md5(str(build_id)))
        else:
            bookspace = self.get_book_space(name)

        def parse_register(record):
            register = record.get('register')
            if not register:
                return record

            c_ids = map(lambda i: ObjectId(i), register)
            cfg_records = Configuration.find({'_id': {'$in': list(c_ids)}})
            if not cfg_records:
                return record

            try:
                variables = {}
                content = yaml.safe_load(record.get('content', ''))
                if not content:
                    return record

                vault = Vault({'vault_pass': config.vault.get('secret')})
                for cfg in cfg_records:
                    config_vars = cfg.get('variables')
                    if not config_vars:
                        continue

                    for k, v in config_vars.items():
                        key = '_'.join(['ECLOGUE', 'CONFIG', cfg.get('name', ''), k])
                        is_encrypt = Vault.is_encrypted(v)
                        value = v
                        if is_encrypt:
                            value = vault.decrypt_string(value)

                        variables[key] = value

                content = dict(content)
                content.update(variables)
                record['content'] = yaml.safe_dump(content)
            except Exception as e:
                print(e)

            return record

        self.check_workspace(path=self._check_make(bookspace))
        for item in files:
            item = parse_register(item)
            if roles and item.get('project'):
                project = item.get('project')
                if project and project not in roles:
                    continue
            filename = bookspace + item.get('path')
            print(filename)
            # continue
            # print(filename)
            if item['is_dir']:
                if os.path.isdir(filename):
                    continue

                self.mkdir(filename)
            else:
                if os.path.isfile(filename):
                    file_hash = file_md5(filename)
                    if item.get('md5') and item['md5'] == file_hash:
                        continue
                dirname = os.path.dirname(filename)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if item['is_edit']:
                    Model.build_model('playbooks').update_one({'_id': item['_id']}, {
                        '$set': {
                            'md5': md5(item['content'])
                        }
                    })
                    with open(filename, 'w') as stream:
                        stream.write(item['content'])
                else:
                    with open(filename, 'wb') as stream:
                        db.fs_bucket().download_to_stream(item['file_id'], stream)
        return bookspace

    def _get_role(self, pathname):
        path_split = pathname.lstrip('/').split('/')
        path_len = len(path_split)
        meta = dict()
        if path_len is 1:
            filename = path_split[0] or 'root'
            if filename.find('hosts') >= 0:
                meta['role'] = 'hosts'
            elif filename.find('entry') >= 0:
                meta['role'] = 'entry'
            else:
                meta['role'] = path_split[0] or 'unknown'
                meta['name'] = path_split[0] or 'unknown'
        elif path_len is 2:
            meta['role'] = path_split[0]
            meta['name'] = path_split[1]
        elif path_len >= 3:
            meta['role'] = path_split[2]
            meta['name'] = path_split[path_len - 1]
            meta['project'] = path_split[1]
        return meta

    @staticmethod
    def mkdir(path, mode=0o700):
        if not path or os.path.exists(path):
            return []

        (head, tail) = os.path.split(path)
        res = Workspace.mkdir(head, mode)
        os.mkdir(path)
        os.chmod(path, mode)
        res += [path]

        return res

    @staticmethod
    def get_meta(pathname):
        pathname = pathname.rstrip('/')
        root_path, filename = os.path.split(pathname)
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

    def build_book_from_history(self, build_id):
        history = db.collection('build_history').find_one({'_id': ObjectId(build_id)})
        task_id = history.get('task_id')
        file_id = history.get('file_id')
        job_info = history.get('job_info')
        book = Book.find_one({'_id': ObjectId(job_info.get('book_id'))})
        bookspace = self.get_book_space(book.get('name'))
        bookspace = os.path.join(bookspace, md5(str(task_id)))
        self.mkdir(bookspace)
        save_file = NamedTemporaryFile(delete=False, suffix='.zip').name
        with open(save_file, 'wb') as fd:
            db.fs_bucket().download_to_stream(ObjectId(file_id), fd)

        extract(save_file, bookspace)
        os.unlink(save_file)

        return bookspace
    
        

