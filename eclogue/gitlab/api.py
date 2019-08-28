import os
import zipfile

from gitlab import Gitlab
from eclogue.config import config
from eclogue.lib.workspace import Workspace


class GitlabApi(object):

    def __init__(self, cfg=None):
        if not cfg:
            self._config = config.gitlab
        else:
            self._config = cfg

        base_url = self._config.get('base_url')
        token = self._config.get('token')
        self._gitlab = Gitlab(base_url, private_token=token)

    @property
    def gitlab(self):
        return self._gitlab

    @property
    def config(self):
        return self._config

    @property
    def projects(self):
        return self.gitlab.projects

    def job_space(self, name):
        job_space = self._config.get('job_space')
        if job_space and os.path.isdir(job_space):
            return self._config.get('job_space')

        prefix = config.workspace.get('job')

        return os.path.join(prefix, 'gitlab', name)

    def build_space(self, name):
        job_space = self._config.get('build_space')
        if job_space and os.path.isdir(job_space):
            return self._config.get('build_space')

        prefix = config.workspace.get('build')

        return os.path.join(prefix, 'gitlab', name)

    def get_job(self, job_id):
        pass

    def dowload_artifact(self, project_id, job_id, store):
        # project_id = '13539397'
        # job_id = '261939258'
        project = self.projects.get(project_id)
        # pipeline = project.jobs.get(job_id)
        jobs = project.jobs
        job = jobs.get(job_id)
        if job.status != 'success':
            raise Exception('gitlab job status must be success, %s got'.format(job.status))

        print(job.status)
        with open(store, "wb") as f:
            job.artifacts(streamed=True, action=f.write)

        with zipfile.ZipFile(store, "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(store))
            os.unlink(store)

        return True

    def install(self, workspace='job'):
        project_id = self.config.get('project_id')
        job_id = self.config.get('job_id')
        if workspace == 'job':
            home_path = self.job_space(project_id)
        else:
            home_path = self.build_space(project_id)

        Workspace.mkdir(home_path)
        store = home_path + '/' + job_id + '.zip'
        result = self.dowload_artifact(project_id, job_id, store)
        if not result:
            raise Exception('gitlab download artifacts failed')

        return home_path

