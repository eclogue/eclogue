import os
import yaml
import functools
from collections import namedtuple
from dotenv import load_dotenv, find_dotenv
from jinja2 import Template


APP_ROOT = os.path.abspath(os.getcwd())
CONFIG_PATH = os.path.join(APP_ROOT, 'config')


def get_env_value(key, default_value=''):
    return os.environ.get(key, default_value)


def singleton(cls):
    """ Use class as singleton. """

    cls.__new_original__ = cls.__new__

    @functools.wraps(cls.__new__)
    def singleton_new(cls, *args, **kw):
        it = cls.__dict__.get('__it__')
        if it is not None:
            return it

        cls.__it__ = it = cls.__new_original__(cls, *args, **kw)
        it.__init_original__(*args, **kw)
        return it

    cls.__new__ = singleton_new
    cls.__init_original__ = cls.__init__
    cls.__init__ = object.__init__

    return cls


@singleton
class Config(object):
    _config = None

    def __new__(cls):
        if cls._config is None:
            cls._config = Config.load()
        return object.__new__(cls)

    @staticmethod
    def load():
        load_dotenv(find_dotenv())
        env = os.getenv('ENV') or 'development'
        cfg = {
            'app_root': APP_ROOT,
            'env': env,
            'DEBUG': (True if env is 'development' else False)
        }

        default_file = os.path.join(CONFIG_PATH, 'default.yaml')
        if os.path.isfile(default_file):
            with open(default_file, 'r') as stream:
                template = stream.read()
                template = Template(template)
                content = template.render(home_path=APP_ROOT)
                default = yaml.load(content)
                cfg = cfg.copy()
                cfg.update(default)

        env_file = os.path.join(CONFIG_PATH, env + '.yaml')
        if os.path.isfile(env_file):
            with open(env_file, 'r') as stream:
                template = stream.read()
                template = Template(template)
                content = template.render(home_path=APP_ROOT)
                cnf = yaml.load(content)
                cfg.update(cnf)

        return namedtuple('Config', cfg.keys())(*cfg.values())

    def export(self):
        return self._config


config = Config().export()


