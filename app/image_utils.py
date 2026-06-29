import os
import uuid
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'app/static/uploads'


def process_and_save_image(file_obj, album_id):
    album_folder = os.path.join(UPLOAD_FOLDER, str(album_id))
    os.makedirs(album_folder, exist_ok=True)

    filename = secure_filename(file_obj.filename)
    base_name, _ = os.path.splitext(filename)
    unique_id = str(uuid.uuid4())[:8]

    # Пути
    orig_name = f"{base_name}_{unique_id}_orig.jpg"
    opt_name = f"{base_name}_{unique_id}_opt.webp"
    thumb_name = f"{base_name}_{unique_id}_thumb.webp"

    orig_path = os.path.join(album_folder, orig_name)
    opt_path = os.path.join(album_folder, opt_name)
    thumb_path = os.path.join(album_folder, thumb_name)

    # 1. Сохраняем оригинал
    file_obj.save(orig_path)

    # Открываем для обработки
    with Image.open(orig_path) as img:
        # Применяем EXIF-ориентацию — фото хранится уже в правильном повороте
        img = ImageOps.exif_transpose(img)

        # Конвертируем в RGB если нужно (для WebP)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Запоминаем реальные размеры (после поворота, до ресайза)
        img_width, img_height = img.size

        # 2. Оптимизированная версия (макс 2560px по большей стороне)
        # Копируем, чтобы не испортить оригинальный объект для thumbnail
        opt_img = img.copy()
        opt_img.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        opt_img.save(opt_path, 'WEBP', quality=90)

        # 3. Thumbnail (для сетки) — делаем из исходного, не из уже уменьшенного
        thumb_img = img.copy()
        thumb_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        thumb_img.save(thumb_path, 'WEBP', quality=85)

    return orig_name, opt_name, thumb_name, img_width, img_height