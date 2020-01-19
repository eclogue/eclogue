import uuid
import os
from eclogue.config import config
from tests.basecase import BaseTestCase
from bson import ObjectId
from tests.utils import get_data_set_file
from eclogue.lib.workspace import Workspace
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook


class TestWorkspace(BaseTestCase):

    def setUp(self):
        super().setUp()

    def test_import_playbook_from_dir(self):
        book = self.get_data('book')
        self.add_data(Book, book)
        book_id = str(book['_id'])
        try:
            wk = Workspace()
            home_path = os.path.dirname(wk.get_book_space(book['name']))
            result = wk.import_book_from_dir(home_path,
                                             str(book_id),
                                             prefix='/')
            self.assertIs(len(result) > 0, True)
        finally:
            Playbook().collection.delete_many({'book_id': book_id})



