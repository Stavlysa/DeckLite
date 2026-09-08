import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from bundle_container_apk import embed, verify, MANIFEST


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "base.apk"
        with zipfile.ZipFile(self.base, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("classes.dex", b"app bytes")
            z.writestr("META-INF/CERT.RSA", b"old signature")
            z.writestr("META-INF/library.kotlin_module", b"retained metadata")
        self.rootfs = self.root / "rootfs.tar.zst"
        self.rootfs.write_bytes(b"verified sample rootfs" * 17)
        self.sha = hashlib.sha256(self.rootfs.read_bytes()).hexdigest()
        self.output = self.root / "bundled.apk"

    def build(self, sha=None):
        return embed(self.base, self.rootfs, self.output, sha or self.sha, chunk=64)

    def test_multichunk_roundtrip_strips_only_signatures(self):
        result = self.build()
        self.assertEqual(result["parts"], 6)
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read("classes.dex"), b"app bytes")
            self.assertIn("META-INF/library.kotlin_module", z.namelist())
            self.assertNotIn("META-INF/CERT.RSA", z.namelist())
            self.assertIn(MANIFEST, z.namelist())
        self.assertTrue(verify(self.output, self.sha)["zip32"])

    def test_bad_hash_cleans_only_new_output(self):
        with self.assertRaises(ValueError):
            self.build("0" * 64)
        self.assertFalse(self.output.exists())
        self.assertTrue(self.base.exists())
        self.assertTrue(self.rootfs.exists())

    def test_never_overwrites_existing_output(self):
        self.output.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_refuses_already_bundled_base(self):
        with zipfile.ZipFile(self.base, "a") as z:
            z.writestr(MANIFEST, b"existing")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_verification_rejects_wrong_digest(self):
        self.build()
        with self.assertRaises(ValueError):
            verify(self.output, "0" * 64)


if __name__ == "__main__":
    unittest.main()
