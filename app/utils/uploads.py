from fastapi import UploadFile

from app.exceptions import BadRequestError

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


async def read_image_upload(upload: UploadFile) -> tuple[bytes, str]:
    if upload.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise BadRequestError("Images must be JPEG, PNG, or WebP")
    content = await upload.read()
    if not content:
        raise BadRequestError("Uploaded image is empty")
    return content, ALLOWED_IMAGE_CONTENT_TYPES[upload.content_type]
