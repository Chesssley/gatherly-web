MB = 1024 * 1024


UPLOAD_LIMITS = {
    "avatar": {
        "label": "头像",
        "max_file_size": 2 * MB,
        "max_files": 1,
        "max_width": 512,
        "max_height": 512,
        "target_format": "webp",
        "quality": 82,
    },
    "activity_cover": {
        "label": "活动图片",
        "max_file_size": 5 * MB,
        "max_files": 1,
        "max_width": 1600,
        "max_height": 900,
        "target_format": "webp",
        "quality": 82,
    },
    "activity_images": {
        "label": "活动图片",
        "max_file_size": 5 * MB,
        "max_files": 6,
        "max_long_edge": 1600,
        "target_format": "webp",
        "quality": 82,
    },
    "post_images": {
        "label": "帖子图片",
        "max_file_size": 5 * MB,
        "max_files": 9,
        "max_long_edge": 1600,
        "target_format": "webp",
        "quality": 82,
    },
    "comment_images": {
        "label": "评论图片",
        "max_file_size": 3 * MB,
        "max_files": 3,
        "max_long_edge": 1280,
        "target_format": "webp",
        "quality": 80,
    },
    "message_images": {
        "label": "私信图片",
        "max_file_size": 3 * MB,
        "max_files": 3,
        "max_long_edge": 1280,
        "target_format": "webp",
        "quality": 80,
    },
    "circle_avatar": {
        "label": "圈子头像",
        "max_file_size": 2 * MB,
        "max_files": 1,
        "max_width": 512,
        "max_height": 512,
        "target_format": "webp",
        "quality": 82,
    },
    "circle_cover": {
        "label": "圈子封面",
        "max_file_size": 5 * MB,
        "max_files": 1,
        "max_width": 1600,
        "max_height": 900,
        "target_format": "webp",
        "quality": 82,
        "allowed_extensions": {"jpg", "jpeg", "png", "webp"},
    },
    "merchant_verification": {
        "label": "认证材料",
        "max_file_size": 8 * MB,
        "max_files": 1,
        "allowed_extensions": {"jpg", "jpeg", "png", "webp", "pdf"},
        "max_long_edge": 2000,
        "target_format": "webp",
        "quality": 88,
    },
}


def upload_limit(name):
    return UPLOAD_LIMITS[name]


def size_mb(size):
    return max(1, size // MB)
