import os
import docker
import uuid

from eclogue.config import config
from eclogue.utils import extract, md5
from eclogue.lib.workspace import Workspace


class Docker(object):

    def __init__(self, options):
        self._config = config.docker if hasattr(config, 'docker') else dict()
        self.options = options
        self.image = self.get_image(options.get('image'))
        self.client = Docker.get_client(self.options.get('base_url'))
        self.container = None

    @property
    def config(self):
        return self._config

    @staticmethod
    def get_image(image):
        image = image.split(':')
        if len(image) is 1:
            image[1] = 'lastest'

        return ':'.join(image)

    @staticmethod
    def get_client(sock=None):

        if sock:
            return docker.DockerClient(base_url=sock)

        return docker.from_env()

    def pull(self, repository, tag=None, **kwargs):

        return self.client.images.pull(repository, tag, kwargs)

    def _create(self, image, command=None, working_dir=None, **kwargs):
        self.container = self.client.containers.create(image, command=command, detach=True, working_dir=working_dir, **kwargs)

    def run(self, command, stdout=True, **kwargs):
        print(self.image, kwargs)
        return self.client.containers.run(image=self.image, command=command, stdout=stdout, **kwargs)

    def get_archive(self, path, chunk_size=2097152):
        if not self.container:
            self._create(self.image)

        return self.container.get_archive(path, chunk_size=chunk_size)

    def kill(self):
        if self.container:
            self.container.kill()

    def job_space(self, name):
        job_space = self._config.get('job_space')
        if job_space and os.path.isdir(job_space):
            return self._config.get('job_space')

        prefix = config.workspace.get('job')

        return os.path.join(prefix, 'docker', name)

    def build_space(self, name):
        job_space = self._config.get('build_space')
        if job_space and os.path.isdir(job_space):
            return self._config.get('build_space')

        prefix = config.workspace.get('build')

        return os.path.join(prefix, 'docker', name)

    def install(self, workspace='job'):
        app_path = self.image.replace(':', '/')
        if workspace == 'job':
            home_path = self.job_space(app_path)
        else:
            home_path = self.build_space(app_path)

        working_dir = self.config.get('working_dir')
        Workspace.mkdir(home_path)
        filename = md5(str(uuid.uuid4()))
        store = home_path + '/' + filename + '.tar'
        with open(store, 'wb') as tar:
            bits, stat = self.get_archive(working_dir)
            for chunk in bits:
                tar.write(chunk)

            extract(store, home_path)
            os.unlink(store)
            # @todo store to mongodb gridfs
            if self.config.get('task_id'):
                pass
