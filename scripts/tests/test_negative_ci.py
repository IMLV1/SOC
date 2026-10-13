import unittest

class NegativeCI(unittest.TestCase):
    def test_intentional_verification_failure(self):
        self.fail("Intentional isolated CI failure probe; never merge this PR.")
