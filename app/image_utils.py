import os
import uuid
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'app/static/uploads'


def process_and_save_image_sync(file_obj, album_id):
    album_folder = os.path.join(UPLOAD_FOLDER, str(album_id))
    os.makedirs(album_folder, exist_ok=True)

    filename = secure_filename(file_obj.filename)
    base_name, _ = os.path.splitext(filename)
    unique_id = str(uuid.uuid4())[:8]

    orig_name = f"{base_name}_{unique_id}_orig.jpg"
    name_400w = f"{base_name}_{unique_id}_400w.webp"
    name_800w = f"{base_name}_{unique_id}_800w.webp"
    name_1600w = f"{base_name}_{unique_id}_1600w.webp"

    orig_path = os.path.join(album_folder, orig_name)

    # 1. Сохраняем оригинал мгновенно
    file_obj.save(orig_path)

    # Быстро узнаем размеры, не загружая в память для ресайза
    with Image.open(orig_path) as img:
        img = ImageOps.exif_transpose(img)
        img_width, img_height = img.size

    return orig_name, name_400w, name_800w, name_1600w, img_width, img_height


def process_image_background(app, photo_id, orig_path, path_400w, path_800w, path_1600w):
    """Фоновая задача для генерации превью."""
    with app.app_context():
        # Импортируем внутри, чтобы избежать циклических импортов
        from .models import db, Photo
        
        try:
            with Image.open(orig_path) as img:
                # ВАЖНО: Извлекаем ICC профиль ДО любых трансформаций
                icc = img.info.get('icc_profile')
                
                img = ImageOps.exif_transpose(img)
                
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # 1600w for lightbox initial load
                img_1600 = img.copy()
                img_1600.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                img_1600.save(path_1600w, 'WEBP', quality=100, method=6, icc_profile=icc)

                # 800w for retina grid
                img_800 = img.copy()
                img_800.thumbnail((800, 800), Image.Resampling.LANCZOS)
                img_800.save(path_800w, 'WEBP', quality=100, method=6, icc_profile=icc)

                # 400w for standard grid
                img_400 = img.copy()
                img_400.thumbnail((400, 400), Image.Resampling.LANCZOS)
                img_400.save(path_400w, 'WEBP', quality=100, method=6, icc_profile=icc)
            
            # Обновляем статус фото в БД
            photo = Photo.query.get(photo_id)
            if photo:
                photo.status = 'ready'
                db.session.commit()
                
        except Exception as e:
            print(f"Error processing image {photo_id}: {e}")
            # Можно установить статус 'error' если нужно