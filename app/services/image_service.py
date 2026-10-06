from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    resized: bool

    @property
    def preview_data_url(self) -> str:
        return f"data:{self.mime_type};base64,{b64encode(self.data).decode('ascii')}"


async def read_bounded_upload(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await upload.read(min(64 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ImageValidationError(f"圖片檔案不可超過 {max_bytes // (1024 * 1024)} MiB。")
            chunks.append(chunk)
    finally:
        await upload.close()
    if not chunks:
        raise ImageValidationError("未收到有效的圖片資料。")
    return b"".join(chunks)


def process_image(data: bytes, max_pixels: int, longest_edge: int) -> ProcessedImage:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ImageValidationError("僅支援 JPEG、PNG 或 WebP 圖片。")
            if getattr(source, "n_frames", 1) != 1 or getattr(source, "is_animated", False):
                raise ImageValidationError("不支援動態圖片，請選擇單張靜態圖片。")
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise ImageValidationError(f"圖片解碼後不可超過 {max_pixels:,} 像素。")
            source.load()
            corrected = ImageOps.exif_transpose(source)
            if corrected.mode in {"RGBA", "LA"} or "transparency" in corrected.info:
                rgba = corrected.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                stable = background
            else:
                stable = corrected.convert("RGB")

            resized = max(stable.size) > longest_edge
            if resized:
                stable.thumbnail((longest_edge, longest_edge), Image.Resampling.LANCZOS)
            output = BytesIO()
            stable.save(output, format="JPEG", quality=90, optimize=True)
            return ProcessedImage(
                data=output.getvalue(),
                mime_type="image/jpeg",
                width=stable.width,
                height=stable.height,
                resized=resized,
            )
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ImageValidationError("圖片已損毀、格式不受支援，或內容無法解碼。") from exc


async def validate_and_process_upload(
    upload: UploadFile, max_bytes: int, max_pixels: int, longest_edge: int
) -> ProcessedImage:
    data = await read_bounded_upload(upload, max_bytes)
    return process_image(data, max_pixels, longest_edge)
