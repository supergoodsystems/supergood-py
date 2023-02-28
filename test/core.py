import unittest

class SupergoodTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass
    'testing success states'
        'captures all outgoing 200 http requests'
        'captures non-success status and errors'

    'testing failure states'
        'hanging response'
        'posting errors'

    'config specifications'
        'hasing'
        'not hashing'
        'keys to hash not in config'
        'ignores requests to ignored domains'
        'operates normally when ignored domains is empty'

    'testing various endpoints and libraries basic functionality'
        '<different http libraries>'


    def test_something(self):
        pass

if __name__ == '__main__':
    unittest.main()
