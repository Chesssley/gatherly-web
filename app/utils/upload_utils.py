from werkzeug.utils import secure_filename

from app.services.storage import (
    ALLOWED_IMAGE_EXTENSIONS,
    delete_stored_files,
    upload_file,
)


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
    return False


def validate_image_files(files, max_count, max_bytes):
    selected_files = [file for file in files if file and file.filename]
    if len(selected_files) > max_count:
        raise ValueError(f"最多只能上传 {max_count} 张图片。")

    validated_files = []
    for file in selected_files:
        original_filename = secure_filename(file.filename)
        if "." not in original_filename:
            raise ValueError("图片格式不支持，请上传 jpg、jpeg、png、webp 或 gif 图片。")

        extension = original_filename.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("图片格式不支持，请上传 jpg、jpeg、png、webp 或 gif 图片。")

        content = file.stream.read(max_bytes)
        file.stream.seek(0)
        if not content:
            raise ValueError("图片文件不能为空。")
        if len(content) >= max_bytes:
            raise ValueError(f"单张图片必须小于 {max_bytes // 1024}KB。")
        if not _content_matches_extension(content, extension):
            raise ValueError("图片文件内容与格式不匹配，请重新选择图片。")

        validated_files.append((file, extension))

    return validated_files


def save_image_files(validated_files, upload_subdir):
    saved_paths = []
    try:
        for file, extension in validated_files:
            saved_paths.append(upload_file(file, upload_subdir, extension=extension))
    except RuntimeError as exc:
        delete_saved_images(saved_paths)
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        delete_saved_images(saved_paths)
        raise ValueError("图片保存失败，请稍后重试。") from exc

    return saved_paths


def delete_saved_images(image_paths):
    delete_stored_files(image_paths)
