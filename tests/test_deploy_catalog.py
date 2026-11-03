"""Check deployment artifact compatibility locally, without AWS calls or SDK imports."""

from __future__ import annotations

import importlib
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from mragentbench.catalog import load_catalog


class DeploymentCatalogTest(unittest.TestCase):
    def test_deployment_preserves_cli_catalog_identities_and_hashes(self) -> None:
        with patch("subprocess.run", side_effect=AssertionError("deployment catalog must not invoke AWS")):
            deploy = importlib.import_module("infra.deploy")
            deployed = deploy.catalog()
            local = load_catalog()
        self.assertEqual(len(deployed), 88)
        self.assertEqual(set(deployed), set(local))
        for instance, entry in deployed.items():
            with self.subTest(instance=instance):
                self.assertEqual(entry, {key: local[instance][key] for key in entry})
                for key in ("family", "instance", "manifest_sha256", "package_sha256", "package_bytes"):
                    self.assertEqual(entry[key], local[instance][key])

    def test_lambda_archive_embeds_the_compatible_catalog(self) -> None:
        with patch("subprocess.run", side_effect=AssertionError("building the archive must not invoke AWS")):
            deploy = importlib.import_module("infra.deploy")
            data, _ = deploy.lambda_zip()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                embedded = json.loads(archive.read("catalog.json"))
            self.assertEqual(embedded, deploy.catalog())


if __name__ == "__main__":
    unittest.main()
