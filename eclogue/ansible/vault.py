from ansible import constants as C
from collections import namedtuple
from ansible.parsing.vault import get_file_vault_secret
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.vault import VaultEditor, VaultLib, VaultSecret, match_encrypt_secret
from eclogue.lib.logger import logger

OPTION_FLAGS = ['verbosity', 'ask_vault_pass', 'vault_password_files', 'vault_ids', 'new_vault_password_file',
                'new_vault_id', 'output_file',
                'encrypt_vault_id']

Options = namedtuple('Options', [
    'verbosity',
    'vault_pass',
    'vault_password_files',
    'vault_ids',
    'new_vault_password_file',
    'new_vault_id',
    'output_file',
    'encrypt_vault_id'
])


def get_default_options():
    options = Options(
        verbosity=1,
        vault_pass=False,
        vault_password_files=[],
        vault_ids=[],
        new_vault_password_file=None,
        new_vault_id=None,
        output_file=None,
        encrypt_vault_id=[]
    )
    return options


class Vault(object):

    def __init__(self, options):
        self.options = get_default_options()
        print('opions', options)
        self.get_options(options)
        self.editor = None
        self.encrypt_secret = None
        self.encrypt_vault_id = None
        self.run()

    def run(self):
        loader = DataLoader()
        vault_ids = self.options.vault_ids
        default_vault_ids = C.DEFAULT_VAULT_IDENTITY_LIST
        vault_ids = default_vault_ids + vault_ids
        encrypt_vault_id = None
        vault_secrets = self.setup_vault_secrets(loader,
                                                 vault_ids=vault_ids,
                                                 vault_password_files=self.options.vault_password_files,
                                                 vault_pass=self.options.vault_pass)
        encrypt_secret = match_encrypt_secret(vault_secrets,
                                              encrypt_vault_id=encrypt_vault_id)

        print(encrypt_secret, encrypt_vault_id, vault_secrets)
        self.encrypt_vault_id = encrypt_secret[0]
        self.encrypt_secret = encrypt_secret[1]
        loader.set_vault_secrets(vault_secrets)
        vault = VaultLib(vault_secrets)
        self.editor = VaultEditor(vault)
        # self.encrypt(self.options.file)

    def get_options(self, options):
        for key, value in options.items():
            item = {key: value}
            self.options = self.options._replace(**item)

    def encrypt(self, file):
        self.editor.encrypt_file(file, self.encrypt_secret,
                                 vault_id=self.encrypt_vault_id,
                                 output_file=self.options.output_file)

    def view(self, file):
        return self.editor.plaintext(file)

    def decrypt(self, files):
        if not self.editor:
            self.run()
        for f in files or ['-']:
            self.editor.decrypt_file(f, output_file=self.options.output_file)

    def decrypt_string(self, text):
        try:
            plaintext = self.editor.vault.decrypt(text)

            return str(plaintext, 'utf-8')
        except Exception as e:
            logger.error('decrypt string execption: ' + str(e), extra={'text': text})
            raise e

    def encrypt_string(self, text):
        text = bytes(text, 'utf-8')
        bytestext = self.editor.encrypt_bytes(text, self.encrypt_secret, vault_id=self.encrypt_vault_id)

        return str(bytestext, 'utf-8')

    def setup_vault_secrets(self, loader, vault_ids, vault_password_files=None, vault_pass=None):
        vault_secrets = []
        vault_password_files = vault_password_files or []
        if C.DEFAULT_VAULT_PASSWORD_FILE:
            vault_password_files.append(C.DEFAULT_VAULT_PASSWORD_FILE)
        vault_ids = Vault.build_vault_ids(vault_ids, vault_password_files, vault_pass)
        for vault_id_slug in vault_ids:
            vault_id_name, vault_id_value = Vault.split_vault_id(vault_id_slug)
            if vault_id_value == 'vault_pass':
                built_vault_id = vault_id_name or C.DEFAULT_VAULT_IDENTITY
                # load password
                vault_secret = VaultSecret(bytes(vault_pass, 'utf-8'))
                vault_secrets.append((built_vault_id, vault_secret))
                loader.set_vault_secrets(vault_secrets)
                continue

            file_vault_secret = get_file_vault_secret(filename=vault_id_value,
                                                      vault_id=vault_id_name,
                                                      loader=loader)
            # an invalid password file will error globally
            file_vault_secret.load()
            if vault_id_name:
                vault_secrets.append((vault_id_name, file_vault_secret))
            else:
                vault_secrets.append((C.DEFAULT_VAULT_IDENTITY, file_vault_secret))

            # update loader with as-yet-known vault secrets
            loader.set_vault_secrets(vault_secrets)

        return vault_secrets

    @staticmethod
    def build_vault_ids(vault_ids,
                        vault_password_files=None,
                        vault_pass=None):
        vault_password_files = vault_password_files or []
        vault_ids = vault_ids or []

        # convert vault_password_files into vault_ids slugs
        for password_file in vault_password_files:
            id_slug = '%s@%s' % (C.DEFAULT_VAULT_IDENTITY, password_file)
            vault_ids.append(id_slug)

        if vault_pass or (not vault_ids):
            id_slug = '%s@%s' % (C.DEFAULT_VAULT_IDENTITY, 'vault_pass')
            vault_ids.append(id_slug)

        return vault_ids

    @staticmethod
    def split_vault_id(vault_id):
        # return (before_@, after_@)
        # if no @, return whole string as after_
        if '@' not in vault_id:
            return (None, vault_id)

        parts = vault_id.split('@', 1)
        ret = tuple(parts)
        return ret

    @staticmethod
    def is_encrypted(data):
        if type(data) != str:
            return False

        header = '$ANSIBLE_VAULT'
        # try:
        #     text = to_text(data, encoding='ascii', errors='strict', nonstring='strict')
        #     b_data = to_bytes(text, encoding='ascii', errors='strict')
        # except (UnicodeError, TypeError):
        #     return False

        if data.startswith(header):
            return True
        return False


class ContentVaultSecret(VaultSecret):

    @property
    def bytes(self):
        return self.bytes
