import json
from pathlib import Path
import tempfile
import unittest
from auth_identity import identity_key, public_identity, fingerprint, registered_key


class IdentityTests(unittest.TestCase):
    def test_persistent_identity_and_registration_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            key = identity_key(state)
            self.assertEqual((state / "identity-rsa").stat().st_mode & 0o777, 0o600)
            self.assertEqual(key.asbytes(), identity_key(state).asbytes())
            self.assertTrue(public_identity(key, "client").endswith(" {client}"))
            self.assertIsNone(registered_key(state, "mac", "client"))
            record = {
                "host": "mac",
                "client_id": "client",
                "confirmed": True,
                "key_fingerprint": fingerprint(key),
            }
            (state / "key-registration.json").write_text(json.dumps(record))
            self.assertEqual(
                registered_key(state, "mac", "client").asbytes(), key.asbytes()
            )
            self.assertIsNone(registered_key(state, "different-host", "client"))
            record["key_fingerprint"] = "wrong"
            (state / "key-registration.json").write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                registered_key(state, "mac", "client")


if __name__ == "__main__":
    unittest.main()
