from ansible.parsing.dataloader import DataLoader
import yaml
import copy


class YamlLoader(DataLoader):

    def __init__(self):
        super().__init__()
        print(self._basedir)

    def load_from_file(self, file_name, cache=True, unsafe=False):
        data = yaml.load(file_name)

        if unsafe:
            return data
        else:
            # return a deep copy here, so the cache is not affected
            return copy.deepcopy(data)
