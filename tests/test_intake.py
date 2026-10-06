from __future__ import annotations

import io
import unittest
import zipfile

from social_report.intake import InputFile, prepare_campaign_input, unpack_campaign_archive

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic-not-a-real-image"


def make_zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


class IntakeTest(unittest.TestCase):
    def test_direct_file_manifest(self):
        prepared = prepare_campaign_input([InputFile("upload-1", "screen.png", PNG, "image/png")])
        self.assertEqual(prepared[0].mime_type, "image/png")
        self.assertEqual(len(prepared[0].sha256), 64)

    def test_unsupported_direct_file(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            prepare_campaign_input([InputFile("upload-1", "run.exe", b"MZdata")])

    def test_zip_preserves_relative_paths_and_duplicate_names(self):
        content = make_zip(
            [
                ("campaign/alice/screen.png", PNG),
                ("campaign/bob/screen.png", PNG + b"2"),
            ]
        )
        result = unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))
        self.assertEqual(result.root, "campaign")
        self.assertEqual(
            [entry.relative_path for entry in result.files],
            ["campaign/alice/screen.png", "campaign/bob/screen.png"],
        )

    def test_zip_slip_rejected(self):
        content = make_zip([("../escape.png", PNG)])
        with self.assertRaisesRegex(ValueError, "unsafe ZIP entry"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))

    def test_nested_archive_rejected(self):
        content = make_zip([("nested.zip", make_zip([("a.png", PNG)]))])
        with self.assertRaisesRegex(ValueError, "nested archives"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))

    def test_invalid_zip_rejected(self):
        with self.assertRaisesRegex(ValueError, "ZIP"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", b"not-a-zip"))


if __name__ == "__main__":
    unittest.main()
