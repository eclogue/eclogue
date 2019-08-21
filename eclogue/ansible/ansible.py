import os

from ansible import constants as C
from ansible.utils.path import unfrackpath

string_types = str,
integer_types = int,
class_types = type,
text_type = str
binary_type = bytes


class Ansible(object):
    """
      options = {
        'tags': string or list
        'skip_tags': string or list
        'inventory': string or list

      }

    """

    def __init__(self, options, args=None):

        self.options = options
        self.args = args
        if hasattr(self.options, 'tags') and not self.options.tags:
            self.options.tags = ['all']
        if hasattr(self.options, 'tags') and self.options.tags:
            tags = set()
            for tag_set in self.options.tags:
                for tag in tag_set.split(u','):
                    tags.add(tag.strip())
            self.options.tags = list(tags)

        # process skip_tags
        if hasattr(self.options, 'skip_tags') and self.options.skip_tags:
            skip_tags = set()
            for tag_set in self.options.skip_tags:
                for tag in tag_set.split(u','):
                    skip_tags.add(tag.strip())
            self.options.skip_tags = list(skip_tags)

        # process inventory options except for CLIs that require their own processing
        if hasattr(self.options,
                   'inventory') and not self.SKIP_INVENTORY_DEFAULTS:

            if self.options.inventory:

                # should always be list
                if isinstance(self.options.inventory, string_types):
                    self.options.inventory = [self.options.inventory]

                # Ensure full paths when needed
                self.inventory = []
                if ',' not in self.options.inventory:
                    for opt in self.options.inventory:
                        self.inventory.append(opt)
                else:
                    self.inventory.append(self.options.inventory)

                self.options.inventory = [
                    unfrackpath(opt, follow=False) if ',' not in opt else opt
                    for opt in self.options.inventory
                ]
            else:
                self.options.inventory = C.DEFAULT_HOST_LIST
                self.inventory = C.DEFAULT_HOST_LIST
