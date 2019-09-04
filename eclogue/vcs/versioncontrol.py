import os

from git.cmd import Git
from eclogue.lib.workspace import Workspace
from eclogue.lib.logger import logger, get_logger
from eclogue.config import config


class GitDownload(object):

    def __init__(self, options, build_type='job'):
        self.options = options
        repository, project, version = self.parse_repository()
        self.repository = repository
        self.project = project
        self.version = version
        self.cache_dir = Workspace().get_vcs_space('git')
        self.build_type = build_type
        self.workspace = self.cwd
        self.git = Git(working_dir=self.cwd)
        self.refs = None
        self.logger = get_logger('console')

    def job_space(self, *args, **kwargs):
        prefix = config.workspace.get('job')

        return os.path.join(prefix, 'git', self.project)

    def build_spasce(self, *args, **kwargs):
        prefix = config.workspace.get('job')

        return os.path.join(prefix, 'git', self.project)

    @property
    def cwd(self):
        if self.build_type == 'job':
            return self.job_space()
        else:
            return self.build_spasce()

    def is_cached(self):
        try:
            cache_path = self.cache_dir + '/' + self.project
            is_dir = os.path.isdir(cache_path)
            if is_dir:
                result = Git(cache_path).execute(['git', 'rev-parse', '--git-dir'], )
                if result.startswith('.'):
                    return True
                return False
        except Exception:
            return False

    def run_command(self, command, *args, **kwargs):
        if type(command) == str:
            command = command.split(' ')

        self.logger.info(' '.join(command))

        result = self.git.execute(command, *args, **kwargs)
        # self.logger.info(result)

        return result

    def install(self):
        url = self.repository
        dest = self.cwd
        cache_dir = self.cache_dir + '/' + self.project
        self.sync_mirror()
        if not os.path.exists(dest):
            command = [
                'git',
                'clone',
                url,
                dest,
                '--dissociate', '--reference',
                cache_dir
            ]

            Git().execute(command)
            command = ['git', 'remote', 'add', 'eclogue', self.repository]
            self.logger.info('execute command:{}'.format(' '.join(command)))
            self.run_command(command)
            command = ['git', 'fetch', 'eclogue']
            self.run_command(command)
            command = ['git', 'remote', 'set-url', '--push', 'origin', url]
            self.run_command(command)

        branch_name = self.version
        sha, is_branch = self.get_revision_sha(rev=branch_name)
        if is_branch:
            current_branch = self.current_branch()
            if current_branch != self.version:
                track_branch = 'origin/{}'.format(self.version)
                command = ['git', 'checkout', '-B', branch_name, '--track', track_branch]
                self.run_command(command)
                command[3] = 'eclogue/' + branch_name
                self.run_command(command)
        else:
            revision = self.get_revision()
            if revision != self.version:
                command = ['git', 'checkout', '-B', self.version]
                self.run_command(command)
                command = ['git', 'checkout', '-B', 'eclogue/' + self.version]
                self.run_command(command)

        self.update_commit()

        return self.cwd

    def update_commit(self):
        revision = self.get_revision()
        command = ['git', 'reset', '--hard', revision]
        self.run_command(command)

    def get_revision_sha(self, rev):
        cmd = ['git', 'show-ref', rev]
        output = self.run_command(cmd, kill_after_timeout=True)
        refs = {}
        for line in output.strip().splitlines():
            try:
                sha, ref = line.split()
            except ValueError:
                # Include the offending line to simplify troubleshooting if
                # this error ever occurs.
                raise ValueError('unexpected show-ref line: {!r}'.format(line))

            refs[ref] = sha

        branch_ref = 'refs/remotes/origin/{}'.format(rev)
        tag_ref = 'refs/tags/{}'.format(rev)

        sha = refs.get(branch_ref)
        if sha is not None:
            return [sha, True]

        if not sha:
            self.run_command(['git', 'fetch', self.repository, self.version])

        sha = refs.get(tag_ref)

        return [sha, False]

    def resolve_revision(self, rev):
        sha, is_branch = self.get_revision_sha(rev)
        if sha:
            return [sha, is_branch]
        if not sha:
            raise Exception('invalid sha')

    def get_revision(self, rev=None):
        if rev is None:
            rev = 'HEAD'

        commad = ['git', 'rev-parse', rev]
        current_rev = self.run_command(commad)

        return current_rev.strip()

    def parse_repository(self):
        url = self.options.get('repository')
        tag = self.options.get('tag')
        branch = self.options.get('branch')
        sha = self.options.get('sha')
        target = tag or branch or sha
        if url.find('#') < 0:
            project = os.path.basename(url)
            project = project.replace('.git', '')
            target = target or 'master'

            return [url, project, target]
        else:
            result = url.split('#')
            repository, version = result
            project = os.path.basename(repository)
            project = project.replace('.git', '')
            target = target or version

            return [repository, project, target]

    def current_branch(self):
        cmd = ['git', 'symbolic-ref', '-q', 'HEAD']
        output = self.run_command(cmd)
        ref = output.strip()
        if ref.startswith('refs/heads/'):
            return ref[len('refs/heads/'):]

        return None

    def sync_mirror(self):
        dirname = self.cache_dir + '/' + self.project
        if not self.is_cached():
            git = Git(dirname)
            git.execute(['git', 'clone', '--mirror', self.repository, dirname])
            command = ['git', 'remote', 'add', 'eclogue', self.repository]
            git.execute(command)
            self.logger.info(' '.join(command))
            command = ['git', 'remote', 'set-url', '--push', 'origin', self.repository]
            git.execute(command)
            self.logger.info(' '.join(command))
            command = ['git', 'remote', 'update', '--prune', 'origin']
            git.execute(command)
            self.logger.info(' '.join(command))

    def check(self):
        git = Git()
        output = git.execute(['git', 'ls-remote', '--heads', self.repository])
        if output:
            return True

        return False

