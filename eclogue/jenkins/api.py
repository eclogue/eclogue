import re
import os
import time

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.api import search_artifact_by_regexp, install_artifacts
from jenkinsapi.custom_exceptions import UnknownJob, NotFound
from eclogue.config import config
from eclogue.utils import extract, mkdir
from eclogue.model import db
from eclogue.lib.logger import get_logger

class JenkinsApi(object):
    def __init__(self, options=None):
        options = options or config.jenkins['default']
        options['cache'] = True
        self._config = options
        self._jenkins = Jenkins(baseurl=options.get('base_url'),
                              username=options.get('username'),
                              password=options.get('password'))
        self.logger = get_logger('console')

    @property
    def jenkins(self):
        return self._jenkins

    @property
    def config(self):
        return self._config

    def get_builds(self, job_name):
        job = self.jenkins.get_job(job_name)
        last_build = job.get_last_stable_build()
        print(last_build.splite(' #'))

        mjn = last_build.get_master_job_name()
        # search_artifact_by_regexp(re.compile('(.*?).tar.gz'))

        print(mjn)

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

    def install(self, workspace='job'):
        job_name = self.config.get('job_name')
        build_id = self.config.get('build_id')
        if not job_name or not build_id:
            raise Exception('jenins install miss required params')

        if workspace == 'job':
            save_dir = self.job_space(job_name)
        else:
            save_dir = self.build_space(job_name)

        self.logger.info('start install jenkins app')
        mkdir(save_dir)
        self.save_artifacts(save_dir, job_name, build_id=build_id)

        return save_dir

    def save_artifacts(self, save_dir, job_name, build_id=None, strict_validation=False, artifact_name=None):
        is_cache = self.config.get('cache')
        self.logger.info('use cached:{}'.format(is_cache))
        if is_cache:
            cache_files = db.collection('artifacts').find({
                'job_name': job_name,
                'build_id': build_id,
                'app_type': 'jenkins'
            })
            cache_files = list(cache_files)
            if cache_files:
                for record in cache_files:
                    file_id = record.get('file_id')
                    if not file_id:
                        continue

                    msg = 'load file from cached, save_dir:{}, filename:{}'.format(save_dir, record['filename'])
                    self.logger.info(msg)
                    filename = os.path.join(save_dir, record['filename'])
                    with open(filename, 'wb') as stream:
                        db.fs_bucket().download_to_stream(file_id, stream)
                        extract(filename, save_dir)
                        os.unlink(filename)

                return True

        artifacts = self.get_artifacts(job_name, build_id)
        store_files = []
        for artifact in artifacts:
            if artifact_name and artifact.filename != artifact_name:
                continue

            file_path = artifact.save_to_dir(save_dir, strict_validation)
            msg = 'download artifacts from {}, save_dir:{}, filename:{}'
            msg = msg.format(self.config.get('base_url'), save_dir, artifact.filename)
            self.logger.info(msg)
            extract(file_path, save_dir)
            store_files.append({'filename': artifact.filename, 'path': file_path})

        for file in store_files:
            filename = file['filename']
            path = file['path']
            if is_cache:
                with open(path, mode='rb') as stream:

                    file_id = db.save_file(filename=filename, fileobj=stream)
                    store_info = {
                        'app_type': 'jenkins',
                        'file_id': file_id,
                        'job_name': job_name,
                        'build_id': build_id,
                        'filename': os.path.basename(filename),
                        'created_at': time.time()
                    }
                    db.collection('artifacts').insert_one(store_info)

            os.unlink(path)

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


