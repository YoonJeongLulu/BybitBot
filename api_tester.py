import unittest
import bybit_rest

# test
api_key = ""
api_secret = ""


class Test(unittest.TestCase):

    def test_upper(self):
        print(bybit_rest.get_position_list(api_key, api_secret, False, "BTCUSD"))
        #self.assertEqual('foo'.upper(), 'FOO')


if __name__ == '__main__':
    unittest.main()
