import yaml
from ansible import constants as C
from ansible.inventory.manager import InventoryManager
from ansible.utils.path import unfrackpath
from ansible.errors import AnsibleError, AnsibleOptionsError, AnsibleParserError
from eclogue.ansible.plugin import ContentInventoryPlugin
from eclogue.lib.logger import logger



class HostsManager(InventoryManager):

    # def __init__(self, loader, sources=None):
    #     super().__init__(loader=loader, sources=sources)

    def _setup_inventory_plugins(self):
        plugin = ContentInventoryPlugin()
        self._inventory_plugins.append(plugin)
        super()._setup_inventory_plugins()

    def parse_sources(self, cache=False):
        ''' iterate over inventory sources and parse each one to populate it'''
        self._setup_inventory_plugins()
        parsed = False
        # allow for multiple inventory parsing
        for source in self._sources:
            if source:
                if type(source) == str and ',' not in source and not yaml.safe_load(source):
                    source = unfrackpath(source, follow=False)
                parse = self.parse_source(source, cache=cache)
                if parse and not parsed:
                    parsed = True

        if parsed:
            # do post processing
            self._inventory.reconcile_inventory()
        else:
            if C.INVENTORY_UNPARSED_IS_FAILED:
                raise AnsibleError("No inventory was parsed, please check your configuration and options.")
            else:
                print("No inventory was parsed, only implicit localhost is available")

        self._inventory_plugins = []
