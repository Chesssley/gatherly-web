from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.services.storage import (
    ALLOWED_IMAGE_EXTENSIONS,
    delete_stored_files,
    upload_bytes,
)
from app.utils.upload_limits import size_mb, upload_limit


PDF_EXTENSION = "pdf"
PDF_CONTENT_TYPE = "application/pdf"
def _content_matches_extension(content, extension):
    if extension in {"jpg", "jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "webp":
        return (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    if extension == "gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if extension == PDF_EXTENSION:
        return content.startswith(b"%PDF-")
    return False


def _extension_from_file(file):
    original_filename = secure_filename(file.filename or "")
    if "." not in original_filename:
        raise ValueError("文件格式不支持。")
    return original_filename.rsplit(".", 1)[1].lower()


def _format_allowed_extensions(extensions):
    return "、".join(sorted(extensions))


def _read_limited_file(file, config):
    max_file_size = config["max_file_size"]
    label = config.get("label", "文件")
    content = file.stream.read(max_file_size + 1)
    file.stream.seek(0)
    if not content:
        raise ValueError(f"{label}不能为空。")
    if len(content) > max_file_size:
        raise ValueError(f"{label}不能超过 {size_mb(max_file_size)} MB。")
    return content


def _resize_image(image, config):
    image = ImageOps.exif_transpose(image)
    max_width = config.get("max_width")
    max_height = config.get("max_height")
    max_long_edge = config.get("max_long_edge")
    if max_width and max_height:
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    elif max_long_edge and max(image.size) > max_long_edge:
        ratio = max_long_edge / max(image.size)
        image = image.resize(
            (round(image.width * ratio), round(image.height * ratio)),
            Image.Resampling.LANCZOS,
        )
    return image


def _encode_image(content, config):
    target_format = config.get("target_format", "webp").lower()
    quality = int(config.get("quality", 82))
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            image = _resize_image(image, config)
            if target_format == "webp":
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                encoded = BytesIO()
                image.save(
                    encoded,
                    format="WEBP",
                    quality=quality,
                    method=6,
                    optimize=True,
                )
                encoded.seek(0)
                return encoded, "webp", "image/webp"
    except UnidentifiedImageError as exc:
        raise ValueError("图片文件无法读取，请重新选择。") from exc

    raise ValueError("图片压缩失败，请重新选择。")


def validate_upload_files(files, limit_name, required=False):
    config = upload_limit(limit_name)
    max_files = config["max_files"]
    label = config.get("label", "文件")
    allowed_extensions = config.get("allowed_extensions", ALLOWED_IMAGE_EXTENSIONS)

    selected_files = [file for file in files if file and file.filename]
    if required and not selected_files:
        raise ValueError("请选择要上传的文件。")
    if len(selected_files) > max_files:
        unit = "个文件" if "材料" in label else "张图片"
        raise ValueError(f"{label}最多只能上传 {max_files} {unit}。")

    validated_files = []
    for file in selected_files:
        extension = _extension_from_file(file)
        if extension not in allowed_extensions:
            raise ValueError(f"仅支持 {_format_allowed_extensions(allowed_extensions)} 格式。")

        content = _read_limited_file(file, config)
        if not _content_matches_extension(content, extension):
            raise ValueError("文件内容与格式不匹配，请重新选择。")

        if extension == PDF_EXTENSION:
            validated_files.append(
                {
                    "content": BytesIO(content),
                    "extension": PDF_EXTENSION,
                    "content_type": PDF_CONTENT_TYPE,
                }
            )
            continue

        encoded, target_extension, content_type = _encode_image(content, config)
        validated_files.append(
            {
                "content": encoded,
                "extension": target_extension,
                "content_type": content_type,
            }
        )

    return validated_files


def validate_image_files(files, max_count=None, max_bytes=None, limit_name=None):
    if limit_name:
        return validate_upload_files(files, limit_name)
    config = {
        "max_files": max_count,
        "max_file_size": max_bytes,
        "target_format": "webp",
        "quality": 82,
        "allowed_extensions": ALLOWED_IMAGE_EXTENSIONS,
    }
    selected_files = [file for file in files if file and file.filename]
    if len(selected_files) > max_count:
        raise ValueError(f"最多只能上传 {max_count} 个文件。")
    validated_files = []
    for file in selected_files:
        extension = _extension_from_file(file)
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("图片格式不支持，请上传 jpg、jpeg、png、webp 或 gif 图片。")
        content = _read_limited_file(file, config)
        if not _content_matches_extension(content, extension):
            raise ValueError("图片文件内容与格式不匹配，请重新选择图片。")
        encoded, target_extension, content_type = _encode_image(content, config)
        validated_files.append(
            {
                "content": encoded,
                "extension": target_extension,
                "content_type": content_type,
            }
        )
    return validated_files


def save_upload_files(validated_files, upload_subdir):
    saved_paths = []
    try:
        for item in validated_files:
            saved_paths.append(
                upload_bytes(
                    item["content"],
                    upload_subdir,
                    extension=item["extension"],
                    content_type=item["content_type"],
                )
            )
    except RuntimeError as exc:
        delete_saved_images(saved_paths)
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        delete_saved_images(saved_paths)
        raise ValueError("文件保存失败，请稍后重试。") from exc

    return saved_paths


def save_image_files(validated_files, upload_subdir):
    return save_upload_files(validated_files, upload_subdir)


def delete_saved_images(image_paths):
    delete_stored_files(image_paths)
