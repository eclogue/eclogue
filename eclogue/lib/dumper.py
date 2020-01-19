from eclogue.lib.workspace import Workspace
from eclogue.models.playbook import Playbook

def install_book_from_dir(dirname, book_id):
    wk = Workspace()
    bucket = wk.import_book_from_dir(dirname, book_id)
    playbooks = Playbook.find({'book_id': book_id})
    files = map(lambda i: i['path'], bucket)
    paths = map(lambda i: i['path'], playbooks)
    diff = list(set(paths) - set(files))
    for item in diff:
        Playbook.delete_one({'book_id': book_id, 'path': item})

    mapping = {}
    map(lambda i: {mapping['path']: i}, playbooks)
    for item in bucket:
        record = mapping.get(item['path'])
        if not record:
            Playbook.insert_one(item)
            continue
        if record['additions']:
            item['additions'].update(record['additions'])
            Playbook.update_one({'_id': record['_id']}, {'$set': item})




