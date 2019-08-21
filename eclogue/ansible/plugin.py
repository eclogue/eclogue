import yaml
import os
import pprint
from ansible.plugins.inventory.yaml import InventoryModule
from collections import MutableMapping, Callable
from ansible.errors import AnsibleParserError
from ansible.module_utils._text import to_native
from eclogue.config import config


class ContentInventoryPlugin(InventoryModule):
    NAME = 'dict'

    def __init__(self):
        super(ContentInventoryPlugin, self).__init__()
        self._original_path = ''
        self._load_name = 'content_inventory'

    def verify_file(self, path):
        pprint.pprint(path)
        if ContentInventoryPlugin.is_io(path):
            path = path.read()
        if isinstance(path, str):
            for x in yaml.load_all(path):
                print(x)
            return isinstance(yaml.load(path), dict)
        elif isinstance(path, dict):
            return True

    def parse(self, inventory, loader, path, cache=True):
        try:
            if type(path) == str:
                path = path.replace(config.home_path + '/', '')
            super(InventoryModule, self).parse(inventory, loader, path)
            self.set_options()

            try:
                if type(path) == str:
                    data = dict()
                    gen = yaml.load_all(path)
                    for i in gen:
                        data.update(i)
                else:
                    data = path
            except Exception as e:
                raise AnsibleParserError(e)

            if not data:
                raise AnsibleParserError('Parsed empty YAML string')
            elif not isinstance(data, MutableMapping):
                raise AnsibleParserError('YAML inventory has invalid structure, it should be a dictionary, got: %s' % type(data))
            elif data.get('plugin'):
                raise AnsibleParserError('Plugin configuration YAML string, not YAML inventory')

            # We expect top level keys to correspond to groups, iterate over them
            # to get host, vars and subgroups (which we iterate over recursivelly)
            if isinstance(data, MutableMapping):
                for group_name in data:
                    self._parse_group(group_name, data[group_name])
            else:
                raise AnsibleParserError("Invalid data from file, expected dictionary and got:\n\n%s" % to_native(data))

        except Exception as err:
            print(err)

    @staticmethod
    def is_io(f):
        """
        Check if object 'f' is readable file-like
        that it has callable attributes 'read' , 'write' and 'closer'
        """
        try:
            if isinstance(getattr(f, 'read'), Callable) \
                and isinstance(getattr(f, 'write'), Callable) \
                and isinstance(getattr(f, 'close'), Callable):
                return True
        except AttributeError:
            pass
        return False
