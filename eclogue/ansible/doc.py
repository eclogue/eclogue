import time

from collections import namedtuple
import ansible.plugins.loader as plugin_loader
from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleOptionsError
from ansible.cli.doc import DocCLI
from ansible import context
from ansible.utils.context_objects import CLIArgs

from eclogue.model import db

default_options = {
    'list_files': False,
    'verbosity': 0,
    'show_snippet': False,
    'type': 'module',
    'list_dir': False,
    'module_path': None,
    'json_dump': False,
    'all_plugins': False,
}


class AnsibleDoc(DocCLI):

    def __init__(self, args, options=None):
        super().__init__(args)
        self.args = args if type(args) == list else [args]
        self.plugin_list = set()
        options_dict = default_options
        if options:
            options_dict.update(options)

        self.options = options_dict
        context.CLIARGS = CLIArgs(self.options)

    def update_context_args(self, options):
        self.options = self.options.update(options)
        context.CLIARGS = CLIArgs(self.options)

    def store_modules(self):
        self.update_context_args({'json_dump': True})
        result = self.run()
        for key, value in result.items():
            if not value.get('name'):
                for k, v in value.items():
                    v['main'] = key
                    v['parent'] = k
                    v['created_at'] = time.time()
                    where = {
                        'name': v['name']
                    }
                    update = {
                        '$set': v
                    }
                    db.collection('ansible_modules').update_one(where, update=update, upsert=True)
            else:
                value['main'] = key
                value['parent'] = key
                value['created_at'] = time.time()
                where = {
                    'name': value['name']
                }
                update = {
                    '$set': value
                }
                db.collection('ansible_modules').update_one(where, update=update, upsert=True)

        return result

    def run(self):
        plugin_type = self.options.get('type')
        if plugin_type in C.DOCUMENTABLE_PLUGINS:
            loader = getattr(plugin_loader, '%s_loader' % plugin_type)
        else:
            raise AnsibleOptionsError("Unknown or undocumentable plugin type: %s" % plugin_type)

        if self.options.get('module_path'):
            for path in self.options.get('module_path'):
                if path:
                    loader.add_directory(path)

        if self.options.get('json_dump'):
            plugin_data = {}
            for plugin_type in C.DOCUMENTABLE_PLUGINS:
                plugin_data[plugin_type] = dict()
                plugin_names = self.get_all_plugins_of_type(plugin_type)
                for plugin_name in plugin_names:
                    plugin_info = self.get_plugin_metadata(plugin_type, plugin_name)
                    if plugin_info is not None:
                        plugin_data[plugin_type][plugin_name] = plugin_info

            return plugin_data

        search_paths = DocCLI.print_paths(loader)
        loader._paths = None
        text = ''
        for plugin in self.args:
            textret = self.format_plugin_doc(plugin, loader, plugin_type, search_paths)

            if textret:
                text += textret

        return text
