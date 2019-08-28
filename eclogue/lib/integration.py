from eclogue.jenkins.api import JenkinsApi
from eclogue.gitlab.api import GitlabApi
from eclogue.vcs.versioncontrol import GitDownload
from eclogue.docker.client import Docker
from eclogue.lib.logger import logger


class Integration(object):

    def __init__(self, app_type, app_params=None):
        self.app_type = app_type
        self.app_params = app_params
        self.app = self.get_app(app_type, app_params)

    def _check_jenkins_params(self, params):
        job_name = params.get('job_name')
        if not params.get('username'):
            return False

        if not params.get('password'):
            return False

        if not params.get('base_url'):
            return False

        if not job_name:
            return False

        jks = self.app
        job = jks.get_job(job_name)
        if str(job) != job_name:
            return False

        latest_build = jks.get_latest_build(job_name)
        if not latest_build:
            return False

        return True

    def _check_gitlab_params(self, params):
        gitlab = self.app
        project_id = params.get('project_id')
        project = gitlab.projects.get(project_id)
        if not project:
            return False

        return True

    def _check_docker_params(self, params):
        if not params.get('image'):
            return False

        return True

    def _check_git_params(self, params):
        repository = params.get('repository')
        if not repository:
            return False

        try:
            git = self.app
            git.check()

            return True
        except Exception as e:
            logger.error('check git params error: ' + str(e))
            return False

    def check_app_params(self):
        name = self.app_type
        params = self.app_params
        if name == 'jenkins':
            return self._check_jenkins_params(params)
        elif name == 'gitlab':
            return self._check_gitlab_params(params)
        elif name == 'docker':
            return self._check_docker_params(params)
        elif name == 'git':
            return self._check_git_params(params)
        else:
            return True

    def install(self):
        app = self.app
        if hasattr(app, 'install'):
            return app.install()

    @staticmethod
    def get_app(app_type, app_params):
        if app_type == 'jenkins':
            return JenkinsApi(app_params)
        elif app_type == 'gitlab':
            return GitlabApi(app_params)
        elif app_type == 'docker':
            return Docker(app_params)
        elif app_type == 'git':
            return GitDownload(app_params)
        else:
            return True

    def get_job_space(self, job_name):
        app = self.app
        if hasattr(app, 'job_space'):
            return app.job_space(job_name)

        return False

    def get_build_space(self, app_type, job_name):
        app = self.get_app(app_type)
        if hasattr(app, 'build_space'):
            return app.job_space(job_name)

        return False

