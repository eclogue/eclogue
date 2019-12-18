import os
from eclogue.model import Model
from eclogue.lib.helper import get_meta


class Playbook(Model):
    name = 'playbook'

    def rename(self, _id, path):
        record = self.find_by_id(_id)
        if not record:
            return False

        if record.get('is_dir'):
            records = self.find({'book_id': record['book_id'],'parent': record.get('path')})
            for doc in records:
                new_path = doc['path'].replace(doc['parent'], path)
                if doc.get('is_dir'):
                    self.rename(doc['_id'], new_path)
                    continue

                meta = get_meta(new_path)
                update = {
                    'path': new_path,
                    'parent': os.path.dirname(new_path),
                    **meta,
                }
                self.update_one({'_id': doc['_id']}, {'$set': update})

        meta = get_meta(path)
        update = {
            'path': path,
            'parent': os.path.dirname(path),
            **meta,
        }
        self.update_one({'_id': record['_id']}, {'$set': update})

        return True


playbook = Playbook()
