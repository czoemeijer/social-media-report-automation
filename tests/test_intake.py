from __future__ import annotations

import io
import unittest
import zipfile

from PIL import Image

from social_report.intake import (
    InputFile,
    detect_mime,
    prepare_campaign_input,
    unpack_campaign_archive,
    validate_image_decoder,
)


def make_png(color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (2, 2), color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(color=(0, 255, 0)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (2, 2), color)
    img.save(buf, format="JPEG")
    return buf.getvalue()


VALID_PNG = make_png()
VALID_JPEG = make_jpeg()


def make_zip(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


class IntakeTest(unittest.TestCase):
    def test_direct_file_manifest(self):
        prepared = prepare_campaign_input([InputFile("upload-1", "screen.png", VALID_PNG, "image/png")])
        self.assertEqual(prepared[0].mime_type, "image/png")
        self.assertEqual(len(prepared[0].sha256), 64)
        self.assertTrue(prepared[0].transport_name.startswith("sr_"))
        self.assertIn("screen.png", prepared[0].transport_name)

    def test_unsupported_direct_file(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            prepare_campaign_input([InputFile("upload-1", "run.exe", b"MZdata")])

    def test_zip_preserves_relative_paths_and_duplicate_names(self):
        content = make_zip(
            [
                ("campaign/alice/screen.png", VALID_PNG),
                ("campaign/bob/screen.png", make_png(color=(0, 0, 255))),
            ]
        )
        result = unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))
        self.assertEqual(result.root, "campaign")
        self.assertEqual(
            [entry.relative_path for entry in result.files],
            ["campaign/alice/screen.png", "campaign/bob/screen.png"],
        )
        # Ensure transport names are distinct despite identical basenames
        names = [entry.transport_name for entry in result.files]
        self.assertEqual(len(names), 2)
        self.assertNotEqual(names[0], names[1])

    def test_zip_slip_rejected(self):
        content = make_zip([("../escape.png", VALID_PNG)])
        with self.assertRaisesRegex(ValueError, "unsafe ZIP entry"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))

    def test_nested_archive_rejected(self):
        content = make_zip([("nested.zip", make_zip([("a.png", VALID_PNG)]))])
        with self.assertRaisesRegex(ValueError, "nested archives"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", content))

    def test_invalid_zip_rejected(self):
        with self.assertRaisesRegex(ValueError, "ZIP"):
            unpack_campaign_archive(InputFile("zip-1", "campaign.zip", b"not-a-zip"))

    # Finding 2 regression tests: strict byte signatures & Pillow decoder validation
    def test_fake_png_containing_arbitrary_text_rejected(self):
        fake_png = b"Hello, this is just plain text masquerading as PNG."
        self.assertEqual(detect_mime(fake_png, "screen.png"), "application/octet-stream")
        with self.assertRaisesRegex(ValueError, "unsupported file type"):
            prepare_campaign_input([InputFile("f1", "fake.png", fake_png)])

    def test_fake_jpg_containing_zip_data_rejected(self):
        fake_jpg = make_zip([("file.txt", b"secret")])
        self.assertEqual(detect_mime(fake_jpg, "photo.jpg"), "application/zip")
        with self.assertRaisesRegex(ValueError, "unsupported file type"):
            prepare_campaign_input([InputFile("f2", "photo.jpg", fake_jpg)])

    def test_truncated_png_rejected_by_decoder(self):
        # Starts with valid 8-byte PNG header but is truncated
        truncated_png = b"\x89PNG\r\n\x1a\n" + b"incomplete-data"
        with self.assertRaises(ValueError) as ctx:
            validate_image_decoder(truncated_png, "image/png")
        self.assertIn("corrupt, truncated, or unreadable image data", str(ctx.exception))

    def test_corrupt_jpeg_rejected_by_decoder(self):
        # Starts with JPEG SOI marker \xff\xd8 but corrupt body
        corrupt_jpeg = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00corrupt"
        with self.assertRaises(ValueError) as ctx:
            validate_image_decoder(corrupt_jpeg, "image/jpeg")
        self.assertIn("corrupt, truncated, or unreadable image data", str(ctx.exception))

    def test_valid_png_with_wrong_extension_detected_correctly(self):
        # Byte signature proves it's image/png regardless of .jpg filename
        detected = detect_mime(VALID_PNG, "evidence.jpg")
        self.assertEqual(detected, "image/png")
        prepared = prepare_campaign_input([InputFile("f3", "evidence.jpg", VALID_PNG)])
        self.assertEqual(prepared[0].mime_type, "image/png")

    # Finding 9 regression tests: archive size limit
    def test_archive_exceeding_total_uncompressed_limit_rejected(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            # We can test with a low max_total_size parameter
            archive.writestr("a.png", VALID_PNG)
            archive.writestr("b.png", VALID_PNG)
        content = output.getvalue()
        # With max_total_size=50 bytes, two 69-byte PNGs exceed the limit
        with self.assertRaisesRegex(ValueError, "ZIP exceeds total uncompressed size limit"):
            unpack_campaign_archive(InputFile("z1", "test.zip", content), max_total_size=50)


if __name__ == "__main__":
    unittest.main()
