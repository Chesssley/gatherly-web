import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


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
    return False


def validate_image_files(files, max_count, max_bytes):
    selected_files = [file for file in files if file and file.filename]
    if len(selected_files) > max_count:
        raise ValueError(f"最多只能上传 {max_count} 张图片。")

    validated_files = []
    for file in selected_files:
        original_filename = secure_filename(file.filename)
        if "." not in original_filename:
            raise ValueError("图片格式不支持，请上传 jpg、jpeg、png 或 webp 图片。")

        extension = original_filename.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("图片格式不支持，请上传 jpg、jpeg、png 或 webp 图片。")

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
    upload_dir = os.path.join(current_app.static_folder, upload_subdir)
    os.makedirs(upload_dir, exist_ok=True)

    saved_paths = []
    try:
        for file, extension in validated_files:
            filename = secure_filename(f"{uuid4().hex}.{extension}")
            file.save(os.path.join(upload_dir, filename))
            saved_paths.append(f"{upload_subdir.replace(os.sep, '/')}/{filename}")
    except OSError as exc:
        delete_saved_images(saved_paths)
        raise ValueError("图片保存失败，请稍后重试。") from exc

    return saved_paths


def delete_saved_images(image_paths):
    for image_path in image_paths:
        absolute_path = os.path.join(current_app.static_folder, image_path)
        if os.path.isfile(absolute_path):
            try:
                os.remove(absolute_path)
            except OSError:
                pass
