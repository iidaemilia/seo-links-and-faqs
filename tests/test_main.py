"""Tests for command-line analysis modes."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class EmbeddingCliTests(unittest.TestCase):
    """Verify embedding mode reaches reports without a live API request."""

    @patch("main.calculate_embedding_similarities", return_value=[])
    def test_embedding_mode_is_recorded_in_report(
        self,
        mock_calculate_embeddings,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            arguments = [
                "main.py",
                "--site",
                "sample_site",
                "--similarity",
                "embeddings",
                "--out-dir",
                str(output_dir),
            ]
            with (
                patch.object(sys, "argv", arguments),
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            ):
                main.main()

            report = json.loads(
                (output_dir / "report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            report["settings"]["similarity_method"],
            "embeddings",
        )
        self.assertEqual(
            report["settings"]["similarity_model"],
            "text-embedding-3-small",
        )
        self.assertEqual(report["settings"]["min_similarity"], 0.70)
        mock_calculate_embeddings.assert_called_once()


if __name__ == "__main__":
    unittest.main()
