import os
import time

from eclogue.models.book import book
from eclogue.models.playbook import Playbook
from eclogue.lib.workspace import Workspace


def check_playbook(book_id):
    record = book.find_by_id(book_id)
    if not record:
        raise Exception('invalid playbook')

    records = Playbook.find({'book_id': book_id})
    for item in records:
        parent = item.get('parent')
        if not item.get('parent'):
            continue

        p_item = Playbook.find_one({'book_id': book_id, 'path': parent})
        if not p_item:
            p_path = os.path.dirname(parent)
            p_path = p_path if p_path != '/' else None
            data = {
                'path': parent,
                'parent': p_path,
                'is_dir': True,
                'is_edit': False,
                'book_id': book_id,
                'role': os.path.basename(parent),
                'created_at': time.time(),
            }

            meta = Workspace.get_meta(parent)
            data.update(meta)
            data['additions'] = meta
            Playbook.insert_one(data)

    return True
