"""Directory and display-ID migrations must not invalidate the published data catalog."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import unittest

from tools import make_croissant


class CroissantCompatibilityTest(unittest.TestCase):
    def test_catalog_matches_the_published_release(self) -> None:
        rows = make_croissant.catalog_rows()
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=[name for name, _, _ in make_croissant.COLUMNS], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        # core-v0.1.0/catalog.csv is already public. Renaming source folders must not change it.
        self.assertEqual(
            hashlib.sha256(text.getvalue().encode()).hexdigest(),
            "20413f3016bdbd17cafe3ae809450470e3d609040116402502dc2ef8ffaabfcf",
        )

    def test_distribution_exposes_public_aliases_and_existing_source_links(self) -> None:
        aliases = make_croissant.public_instances()
        document = json.loads((make_croissant.REPO / "croissant.json").read_text())
        packages = {entry["name"]: entry for entry in document["distribution"][1:]}
        for row in make_croissant.catalog_rows():
            with self.subTest(instance=row["instance"]):
                identity = aliases[row["instance"]]
                package = packages[row["package"]]
                self.assertIn(identity["alias"], package["description"])
                self.assertIn(row["instance"], package["description"])
                self.assertEqual(package["url"], identity["url"])
                self.assertTrue((make_croissant.REPO / "families" / identity["url"].rsplit("/", 1)[1]).is_dir())
                self.assertEqual(package["sha256"], row["package_sha256"])


if __name__ == "__main__":
    unittest.main()
