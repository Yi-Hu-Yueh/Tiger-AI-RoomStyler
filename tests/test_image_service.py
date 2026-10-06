from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from PIL import Image
from starlette.datastructures import UploadFile

from app.services.image_service import ImageValidationError, process_image, read_bounded_upload
from tests.conftest import make_image


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_supported_static_images(fmt: str) -> None:
    result = process_image(make_image(fmt), 25_000_000, 2048)
    assert result.mime_type == "image/jpeg"
    assert result.width == 80 and result.height == 60
    with Image.open(BytesIO(result.data)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.mode == "RGB"
        assert not decoded.getexif()


def test_corrupt_image() -> None:
    with pytest.raises(ImageValidationError, match="損毀"):
        process_image(b"not-an-image", 25_000_000, 2048)


def test_unsupported_image() -> None:
    with pytest.raises(ImageValidationError, match="僅支援"):
        process_image(make_image("BMP"), 25_000_000, 2048)


def test_oversized_upload_is_bounded() -> None:
    upload = UploadFile(file=BytesIO(b"x" * 101), filename="large.png")
    with pytest.raises(ImageValidationError, match="不可超過"):
        asyncio.run(read_bounded_upload(upload, 100))


def test_excessive_decoded_pixels() -> None:
    with pytest.raises(ImageValidationError, match="像素"):
        process_image(make_image("PNG", (101, 100)), 10_000, 2048)


def test_animated_image_rejected() -> None:
    output = BytesIO()
    frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
    frames[0].save(output, format="WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    with pytest.raises(ImageValidationError, match="動態"):
        process_image(output.getvalue(), 25_000_000, 2048)


def test_exif_orientation_is_applied() -> None:
    image = Image.new("RGB", (40, 20), "red")
    exif = Image.Exif()
    exif[274] = 6
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    result = process_image(output.getvalue(), 25_000_000, 2048)
    assert (result.width, result.height) == (20, 40)


def test_longest_edge_resize_and_aspect_ratio() -> None:
    result = process_image(make_image("PNG", (4000, 2000)), 25_000_000, 2048)
    assert result.resized is True
    assert (result.width, result.height) == (2048, 1024)
