import os
import six
import ansiblelint.formatters as formatters
from collections import namedtuple
from munch import Munch
from ansiblelint import RulesCollection, Runner, default_rulesdir
from ansiblelint.utils import get_playbooks_and_roles, normpath
from eclogue.models.playbook import Playbook
from eclogue.lib.workspace import Workspace
from eclogue.models.book import Book
from eclogue.config import config
from eclogue.lib.builder import build_book_from_db


def get_default_options(args):
    opts = {
        'listrules': False,
        'quiet': False,
        'parseable': False,
        'parseable_severity': False,
        'rulesdir': [],
        'use_default_rules': False,
        'tags': [],
        'listtags': None,
        'verbosity': 0,
        'skip_list': [],
        'colored': True,
        'exclude_paths': [],
        'c': None
    }
    opts.update(args)

    return Munch(opts)


def lint(book_id, options, config=None):
    """
    base on ansiblelint
    refer to ansiblelint.__main__.py
    :param book_id:
    :param options:
    :param config:
    :return: None
    """
    formatter = formatters.Formatter()
    options = get_default_options(options)
    where = {
        'book_id': str(book_id),
        'role': 'entry',
    }
    entries = Playbook.find(where)
    if not entries:
        return False

    book = Book.find_by_id(book_id)
    if not book:
        return False

    if config:
        if 'quiet' in config:
            options.quiet = options.quiet or config['quiet']

        if 'parseable' in config:
            options.parseable = options.parseable or config['parseable']

        if 'parseable_severity' in config:
            options.parseable_severity = options.parseable_severity or \
                                         config['parseable_severity']

        if 'use_default_rules' in config:
            options.use_default_rules = options.use_default_rules or config['use_default_rules']

        if 'verbosity' in config:
            options.verbosity = options.verbosity + config['verbosity']

        options.exclude_paths.extend(
            config.get('exclude_paths', []))

        if 'rulesdir' in config:
            options.rulesdir = options.rulesdir + config['rulesdir']

        if 'skip_list' in config:
            options.skip_list = options.skip_list + config['skip_list']

        if 'tags' in config:
            options.tags = options.tags + config['tags']

    if options.quiet:
        formatter = formatters.QuietFormatter()

    if options.parseable:
        formatter = formatters.ParseableFormatter()

    if options.parseable_severity:
        formatter = formatters.ParseableSeverityFormatter()

    # no args triggers auto-detection mode
    # if len(args) == 0 and not (options.listrules or options.listtags):
    #     args = get_playbooks_and_roles(options=options)

    if options.use_default_rules:
        rulesdirs = options.rulesdir + [default_rulesdir]
    else:
        rulesdirs = options.rulesdir or [default_rulesdir]

    rules = RulesCollection()
    for rulesdir in rulesdirs:
        rules.extend(RulesCollection.create_from_directory(rulesdir))

    if options.listrules:
        print(rules)
        return 0

    if options.listtags:
        print(rules.listtags())
        return 0

    if isinstance(options.tags, six.string_types):
        options.tags = options.tags.split(',')

    skip = set()
    for s in options.skip_list:
        skip.update(str(s).split(','))

    options.skip_list = frozenset(skip)
    with build_book_from_db(book.get('name'), options.get('roles')) as book_path:
        playbooks = []
        for record in entries:
            entry = os.path.join(book_path, record['path'][1:])
            playbooks.append(entry)

        playbooks = sorted(set(playbooks))
        matches = list()
        checked_files = set()
        for playbook in playbooks:
            runner = Runner(rules, playbook, options.tags,
                            options.skip_list, options.exclude_paths,
                            options.verbosity, checked_files)
            matches.extend(runner.run())

        matches.sort(key=lambda x: (normpath(x.filename), x.linenumber, x.rule.id))
        results = []
        for match in matches:
            filename = str(match.filename)
            filename = filename.replace(book_path, '')
            results.append({
                'lineNumber': match.linenumber,
                'line': str(match.line),
                'rule': match.rule.id,
                'filename': filename,
                'message': match.message,
            })

        return results
