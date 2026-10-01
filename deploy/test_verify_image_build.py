import unittest

from verify_image_build import completed_image


class TestImageBuildProof(unittest.TestCase):
    image_id = "sha256:" + "a" * 64
    tag = "realtyna-erpnext-hrms:deploy-test"

    def log(self):
        return f"#17 writing image {self.image_id} done\n#17 naming to docker.io/{self.tag} done\n#17 DONE 4.2s\n"

    def test_complete_matching_image(self):
        self.assertTrue(completed_image(self.log(), self.image_id, self.tag))

    def test_stale_tag_is_not_proof(self):
        self.assertFalse(completed_image(self.log(), "sha256:" + "b" * 64, self.tag))

    def test_incomplete_export_is_not_proof(self):
        self.assertFalse(completed_image(self.log().replace("#17 DONE 4.2s\n", ""), self.image_id, self.tag))

    def test_wrong_tag_is_not_proof(self):
        self.assertFalse(completed_image(self.log(), self.image_id, "different:tag"))

    def test_failure_is_not_proof(self):
        self.assertFalse(completed_image(self.log() + "ERROR: build failed", self.image_id, self.tag))

    def test_containerd_manifest_export(self):
        log = self.log().replace("writing image", "exporting manifest list").replace(" done\n#17 naming", " 0.0s done\n#17 naming")
        self.assertTrue(completed_image(log, self.image_id, self.tag))

    def test_containerd_export_waits_until_unpacking_completes(self):
        log = self.log().replace("writing image", "exporting config").replace("#17 DONE 4.2s\n", "#17 unpacking to docker.io/library/" + self.tag + "\n")
        self.assertFalse(completed_image(log, self.image_id, self.tag))


if __name__ == "__main__":
    unittest.main()
