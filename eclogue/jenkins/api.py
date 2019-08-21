import re
import os

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.api import search_artifact_by_regexp, install_artifacts
from jenkinsapi.custom_exceptions import UnknownJob, NotFound
from eclogue.config import config
from eclogue.utils import extract, mkdir


class JenkinsApi(object):
    def __init__(self, options=None):
        options = options or config.jenkins['default']
        self._config = options
        self.server = Jenkins(baseurl=options.get('base_url'),
                              username=options.get('username'),
                              password=options.get('password'))

    def get_builds(self, job_name):
        job = self.jenkins.get_job(job_name)
        artifacts = job.get_last_stable_build().get_artifacts()
        for artifact in artifacts:
            save_dir = self.job_space(job_name)
            artifact.save_to_dir(save_dir)
        # last_build = job.get_last_stable_build()
        # print(last_build.splite(' #'))

        # mjn = build.get_master_job_name()
        # search_artifact_by_regexp(re.compile('(.*?).tar.gz'))
        # print(mjn)

    @property
    def jenkins(self):
        return self.server

    def job_space(self, name):
        job_space = self._config.get('job_space')
        if job_space and os.path.isdir(job_space):
            return self._config.get('job_space')

        prefix = config.workspace.get('job')

        return os.path.join(prefix, 'jenkins', name)

    def build_space(self, name):
        build_space = self._config.get('build_space')
        if build_space and os.path.isdir(build_space):
            return self._config.get('build_space')

        prefix = config.workspace.get('build')

        return os.path.join(prefix, 'jenkins', name)

    def get_build(self, job_name, build_id=None):
        job = self.jenkins.get_job(job_name)
        if not build_id:
            build_id = job.get_last_stable_build().get_number()
        return job.get_build(int(build_id))

    def get_artifacts(self, job_name, build_id=None):
        build = self.get_build(job_name, build_id)

        return build.get_artifacts()

    def install(self, job_name, build_id, workspace='job'):
        if workspace == 'job':
            save_dir = self.job_space(job_name)
        else:
            save_dir = self.build_space(job_name)

        mkdir(save_dir)
        self.save_artifacts(save_dir, job_name, build_id=build_id)

        return save_dir

    def save_artifacts(self, save_dir, job_name, build_id=None, strict_validation=False, artifact_name=None):
        artifacts = self.get_artifacts(job_name, build_id)
        for artifact in artifacts:
            if artifact_name and artifact.filename != artifact_name:
                continue

            file_path = artifact.save_to_dir(save_dir, strict_validation)
            print('jjjjenkin save artifacts   :: ', file_path)
            extract(file_path, save_dir)
            # os.unlink(file_path)

    def get_job(self, job_name):
        try:
            return self.jenkins.get_job(job_name)
        except UnknownJob:
            return False

    def get_latest_build(self, job_name):
        try:
            job = self.get_job(job_name)
            return job.get_last_stable_build()
        except NotFound:
            return False


