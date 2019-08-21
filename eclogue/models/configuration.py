from eclogue.model import Model
from eclogue.config import config
from eclogue.ansible.vault import Vault


class Configuration(Model):
    name = 'configurations'

    def get_variables(self, ids, decode=False):
        records = self.find_by_ids(ids)
        variables = {}
        vault = Vault({'vault_pass': config.vault.get('secret')})
        for record in records:
            config_vars = record.get('variables')
            if not config_vars:
                continue

            for k, v in config_vars.items():
                key = '_'.join(['ECLOGUE', 'CONFIG', record.get('name', ''), k])
                if not decode:
                    variables[key] = v
                    continue

                is_encrypt = Vault.is_encrypted(v)
                value = v
                if is_encrypt:
                    value = vault.decrypt_string(value)

                variables[key] = value

        return variables

configuration = Configuration()
