import uuid
import os
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook
from eclogue.model import db


class JobTest(BaseTestCase):

    def test_add_job(self):
        pass
