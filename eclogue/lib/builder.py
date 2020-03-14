from contextlib import contextmanager
from eclogue.lib.workspace import Workspace


@contextmanager
def build_book_from_db(name, roles=None, build_id=None, history_id=None):
    bookspace = ''
    wk = Workspace()
    try:
        if history_id:
            bookspace = wk.build_book_from_history(history_id)
        else:
            bookspace = wk.load_book_from_db(name, roles=roles, build_id=build_id)
        yield bookspace
    finally:
        if bookspace:
            wk.remove_directory(bookspace)
