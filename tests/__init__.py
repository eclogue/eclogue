
import unittest
from tests.basecase import BaseTestCase


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(BaseTestCase))

    return test_suite
