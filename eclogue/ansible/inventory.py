import yaml
from ansible import constants as C
from ansible.inventory.manager import InventoryManager
from ansible.utils.path import unfrackpath
from ansible.errors import AnsibleError, AnsibleOptionsError, AnsibleParserError
from eclogue.ansible.plugins.inventory import ContentInventoryPlugin
from eclogue.lib.logger import get_logger

logger = get_logger('console')


class HostsManager(InventoryManager):

    # def __init__(self, loader, sources=None):
    #     super().__init__(loader=loader, sources=sources)

    def _fetch_inventory_plugins(self):
        plugins = [ContentInventoryPlugin()]
        plugins.extend(super()._fetch_inventory_plugins())

        return plugins

    def parse_sources(self, cache=False):
        """ iterate over inventory sources and parse each one to populate it"""
        parsed = False
        # allow for multiple inventory parsing
        for source in self._sources:
            if source:
                if type(source) == str and ',' not in source and not yaml.safe_load(source):
                    source = unfrackpath(source, follow=False)

                print('source:::::??', source)
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
                logger.error("No inventory was parsed, only implicit localhost is available")
