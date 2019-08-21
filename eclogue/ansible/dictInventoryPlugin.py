from collections import MutableMapping
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleParserError
from ansible.module_utils._text import to_native
from eclogue.config import config


class DictInventoryPlugin(BaseInventoryPlugin):
    NAME = 'dict'

    def __init__(self):
        super(DictInventoryPlugin, self).__init__()
        self._original_path = '.'
        self._load_name = 'dict_inventory'

    def verify_file(self, path):
        if type(path) is dict:
            return True
        return False
    
    def parse(self, inventory, loader, path, cache=True):
        try:
            super(BaseInventoryPlugin, self).parse(inventory, loader, '')
            self.set_options()

            try:
                data = path
            except Exception as e:
                raise AnsibleParserError(e)

            if not data:
                raise AnsibleParserError('Parsed empty dict string')
            elif not isinstance(data, MutableMapping):
                raise AnsibleParserError('dict inventory has invalid structure, it should be a dictionary, got: %s' % type(data))
            elif data.get('plugin'):
                raise AnsibleParserError('Plugin configuration dict string, not dict inventory')

            # We expect top level keys to correspond to groups, iterate over them
            # to get host, vars and subgroups (which we iterate over recursivelly)
            if isinstance(data, MutableMapping):
                for group_name in data:
                    self._parse_group(group_name, data[group_name])
            else:
                raise AnsibleParserError("Invalid data from file, expected dictionary and got:\n\n%s" % to_native(data))

        except Exception as err:
            print(err)


