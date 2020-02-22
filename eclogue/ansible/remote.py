import os
import yaml

from collections import namedtuple
from ansible import context
from ansible.galaxy import Galaxy
from ansible.galaxy.api import GalaxyAPI
from ansible.galaxy.role import GalaxyRole
from ansible.errors import AnsibleError, AnsibleOptionsError
from ansible.playbook.role.requirement import RoleRequirement
from eclogue.lib.logger import logger
from eclogue.lib.workspace import Workspace
from eclogue.models.playbook import Playbook
from munch import Munch


class AnsibleGalaxy(object):

    def __init__(self, repo, options=None):
        options = options or {}
        self.repo = repo
        opts = self.default_options()
        opts.update(options)
        context._init_global_context(Munch(opts))
        print(context.CLIARGS)

        Options = namedtuple('Options', sorted(opts))
        self.options = Options(**opts)
        self.galaxy = Galaxy()

    def default_options(self):
        wk = Workspace()
        roles_path = [wk.get_galaxy_space()]

        return {
            'verbosity': 3,
            'force': False,
            'role_file': None,
            'keep_scm_meta': False,
            'roles_path': roles_path,
            'api_server': 'https://galaxy.ansible.com',
            'ignore_certs': True,
            'ignore_errors': False,
            'no_deps': False,
            'offline': False,
        }

    def install(self, book_id):
        """
        copy from ansible-galaxy
        uses the args list of roles to be installed, unless -f was specified. The list of roles
        can be a name (which will be downloaded via the galaxy API and github), or it can be a local .tar.gz file.
        """
        role_file = self.options.role_file
        if len(self.repo) == 0 and role_file is None:
            # the user needs to specify one of either --role-file or specify a single user/role name
            raise AnsibleOptionsError("- you must specify a user/role name or a roles file")

        no_deps = self.options.no_deps
        force = self.options.force

        roles_left = []
        if role_file:
            try:
                f = open(role_file, 'r')
                if role_file.endswith('.yaml') or role_file.endswith('.yml'):
                    try:
                        required_roles = yaml.safe_load(f.read())
                    except Exception as e:
                        raise AnsibleError("Unable to load data from the requirements file: %s" % role_file)

                    if required_roles is None:
                        raise AnsibleError("No roles found in file: %s" % role_file)

                    for role in required_roles:
                        if "include" not in role:
                            role = RoleRequirement.role_yaml_parse(role)
                            if "name" not in role and "scm" not in role:
                                raise AnsibleError("Must specify name or src for role")
                            roles_left.append(GalaxyRole(self.galaxy, **role))
                        else:
                            with open(role["include"]) as f_include:
                                try:
                                    roles_left += [
                                        GalaxyRole(self.galaxy, **r) for r in
                                        (RoleRequirement.role_yaml_parse(i) for i in yaml.safe_load(f_include))
                                    ]
                                except Exception as e:
                                    msg = "Unable to load data from the include requirements file: %s %s"
                                    raise AnsibleError(msg % (role_file, e))
                else:
                    raise AnsibleError("Invalid role requirements file")
                f.close()
            except (IOError, OSError) as e:
                raise AnsibleError('Unable to open %s: %s' % (role_file, str(e)))
        else:
            # roles were specified directly, so we'll just go out grab them
            # (and their dependencies, unless the user doesn't want us to).
            for rname in self.repo:
                role = RoleRequirement.role_yaml_parse(rname.strip())
                roles_left.append(GalaxyRole(self.galaxy, **role))

        installed_role = []
        for role in roles_left:
            # only process roles in roles files when names matches if given
            if role_file and self.repo and role.name not in self.repo:
                print('Skipping role %s' % role.name)
                continue

            # query the galaxy API for the role data

            if role.install_info is not None:
                if role.install_info['version'] != role.version or force:
                    if force:
                        print('- changing role %s from %s to %s' %
                                    (role.name, role.install_info['version'], role.version or "unspecified"))
                        role.remove()
                    else:
                        print('- %s (%s) is already installed - use --force to change version to %s' %
                                    (role.name, role.install_info['version'], role.version or "unspecified"))
                        installed_role.append(role.name)
                        continue
                else:
                    if not force:
                        print('- %s is already installed, skipping.' % str(role))
                        continue

            try:
                installed = role.install()
                if installed and book_id:
                    wk = Workspace()
                    wk.import_book_from_dir(os.path.dirname(role.path), book_id, prefix='/roles')

            except AnsibleError as e:
                print("- %s was NOT installed successfully: %s " % (role.name, str(e)))
                # self.exit_without_ignore()
                continue

            # install dependencies, if we want them
            if not no_deps and installed:
                if not role.metadata:
                    print("Meta file %s is empty. Skipping dependencies." % role.path)
                else:
                    role_dependencies = role.metadata.get('dependencies') or []
                    for dep in role_dependencies:
                        logger.debug('Installing dep %s' % dep)
                        dep_req = RoleRequirement()
                        dep_info = dep_req.role_yaml_parse(dep)
                        dep_role = GalaxyRole(self.galaxy, **dep_info)
                        if '.' not in dep_role.name and '.' not in dep_role.src and dep_role.scm is None:
                            # we know we can skip this, as it's not going to
                            # be found on galaxy.ansible.com
                            continue
                        if dep_role.install_info is None:
                            if dep_role not in roles_left:
                                print('- adding dependency: %s' % str(dep_role))
                                roles_left.append(dep_role)
                            else:
                                print('- dependency %s already pending installation.' % dep_role.name)
                        else:
                            if dep_role.install_info['version'] != dep_role.version:
                                print(
                                    '- dependency %s from role %s differs from already installed version (%s), skipping' %
                                    (str(dep_role), role.name, dep_role.install_info['version']))
                            else:
                                print('- dependency %s is already installed, skipping.' % dep_role.name)

            if not installed:
                print("- %s was NOT installed successfully." % role.name)
                # self.exit_without_ignore()

        for role in installed_role:
            wk = Workspace()
            # wk.import_book_from_dir(self.options.roles_path)
        return 0

    def search(self):
        """
        base ansible.cli.galaxy
        searches for roles on the Ansible Galaxy server
        :return: str text
        """
        page_size = 1000
        search = None
        api = GalaxyAPI(self.galaxy)

        if len(self.repo):
            terms = []
            for i in range(len(self.repo)):
                terms.append(self.repo.pop())
            search = '+'.join(terms[::-1])

        if not search and not self.options.platforms and not self.options.galaxy_tags and not self.options.author:
            raise AnsibleError(
                "Invalid query. At least one search term, platform, galaxy tag or author must be provided.")

        response = api.search_roles(search, platforms=self.options.platforms,
                                    tags=self.options.galaxy_tags, author=self.options.author, page_size=page_size)

        if response['count'] == 0:
            print("No roles match your search.")
            return True

        data = ['']

        if response['count'] > page_size:
            data.append("Found %d roles matching your search. Showing first %s." % (response['count'], page_size))
        else:
            data.append("Found %d roles matching your search:" % response['count'])

        max_len = []
        for role in response['results']:
            max_len.append(len(role['username'] + '.' + role['name']))
        name_len = max(max_len)
        format_str = " %%-%ds %%s" % name_len
        data.append('')
        data.append(format_str % ("Name", "Description"))
        data.append(format_str % ("----", "-----------"))
        for role in response['results']:
            data.append(format_str % (u'%s.%s' % (role['username'], role['name']), role['description']))

        data = '\n'.join(data)

        return data


    def info(self):
        if len(self.repo) == 0:
            # the user needs to specify a role
            raise AnsibleOptionsError("- you must specify a user/role name")

        roles_path = self.options.roles_path

        data = []
        for role in self.repo:

            role_info = {'path': roles_path}
            gr = GalaxyRole(self.galaxy, role)

            install_info = gr.install_info
            if install_info:
                if 'version' in install_info:
                    install_info['intalled_version'] = install_info['version']
                    del install_info['version']
                role_info.update(install_info)

            remote_data = False
            api = GalaxyAPI(self.galaxy)
            if not self.options.offline:
                remote_data = api.lookup_role_by_name(role, False)

            if remote_data:
                role_info.update(remote_data)

            if gr.metadata:
                role_info.update(gr.metadata)

            req = RoleRequirement()
            role_spec = req.role_yaml_parse({'role': role})
            if role_spec:
                role_info.update(role_spec)

            data.append(role_info)

        return data
