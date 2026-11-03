"""
Server-side Image Validation Service for Visual Quality Inspection.
Enforces strict industrial validation rules using Pillow before AI inference.
"""

import io
from pathlib import Path
from typing import Tuple
from PIL import Image

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB = 5,242,880 bytes
MIN_DIMENSION = 64
MAX_DIMENSION = 4096
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ALLOWED_FORMATS = {'JPEG', 'PNG'}


class ImageValidationError(Exception):
    """Raised when an uploaded inspection image fails structural validation."""
    pass


def validate_image(file_obj_or_bytes, filename: str) -> Tuple[str, int, int]:
    """
    Strictly validates image format, content, dimensions, and integrity.

    Args:
        file_obj_or_bytes: Bytes or file-like object containing image data.
        filename: Name of the uploaded file.

    Returns:
        Tuple of (format_name, width, height) e.g. ('PNG', 256, 256).

    Raises:
        ImageValidationError: If any validation rule is violated.
    """
    # 1. Read bytes
    if hasattr(file_obj_or_bytes, 'read'):
        if hasattr(file_obj_or_bytes, 'seek'):
            file_obj_or_bytes.seek(0)
        data = file_obj_or_bytes.read()
        if hasattr(file_obj_or_bytes, 'seek'):
            file_obj_or_bytes.seek(0)
    elif isinstance(file_obj_or_bytes, (bytes, bytearray)):
        data = bytes(file_obj_or_bytes)
    else:
        raise ImageValidationError("Invalid file data type provided.")

    # 2. Check zero-byte file
    if len(data) == 0:
        raise ImageValidationError(f"File '{filename}' is empty (0 bytes).")

    # 3. Check maximum size (5 MiB = 5,242,880 bytes)
    if len(data) > MAX_FILE_SIZE:
        size_mb = len(data) / (1024 * 1024)
        raise ImageValidationError(
            f"File '{filename}' exceeds maximum allowed size of 5 MiB ({size_mb:.2f} MiB)."
        )

    # 4. Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            f"Unsupported file extension '{ext}' for '{filename}'. Only JPEG (.jpg, .jpeg) and PNG (.png) files are accepted."
        )

    # 5. Decode actual image content using Pillow
    try:
        # Protect against decompression bombs
        Image.MAX_IMAGE_PIXELS = MAX_DIMENSION * MAX_DIMENSION * 4
        
        # Verify image integrity
        img_verify = Image.open(io.BytesIO(data))
        real_format = img_verify.format
        if real_format not in ALLOWED_FORMATS:
            raise ImageValidationError(
                f"File '{filename}' content is of type '{real_format}', but only JPEG and PNG are allowed."
            )
        
        # img.verify() checks header and data integrity
        img_verify.verify()

        # Re-open for dimension inspection because verify() can close or alter image object
        img = Image.open(io.BytesIO(data))
        width, height = img.size

        # 6. Check dimensions (64 to 4096 px)
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            raise ImageValidationError(
                f"Image dimensions ({width}x{height} px) for '{filename}' are below the minimum required {MIN_DIMENSION}x{MIN_DIMENSION} px."
            )

        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            raise ImageValidationError(
                f"Image dimensions ({width}x{height} px) for '{filename}' exceed the maximum allowed {MAX_DIMENSION}x{MAX_DIMENSION} px."
            )

        return real_format, width, height

    except ImageValidationError:
        raise
    except Image.DecompressionBombError:
        raise ImageValidationError(f"Image '{filename}' exceeds safe decompression limits (decompression bomb detected).")
    except Exception as e:
        raise ImageValidationError(f"File '{filename}' is corrupted or not a valid image: {str(e)}")

