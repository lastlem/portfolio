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
    opt_name = f"{base_name}_{unique_id}_opt.webp"
    thumb_name = f"{base_name}_{unique_id}_thumb.webp"

    orig_path = os.path.join(album_folder, orig_name)

    # 1. Сохраняем оригинал мгновенно
    file_obj.save(orig_path)

    # Быстро узнаем размеры, не загружая в память для ресайза
    with Image.open(orig_path) as img:
        img = ImageOps.exif_transpose(img)
        img_width, img_height = img.size

    return orig_name, opt_name, thumb_name, img_width, img_height


def process_image_background(app, photo_id, orig_path, opt_path, thumb_path):
    """Фоновая задача для генерации превью."""
    with app.app_context():
        # Импортируем внутри, чтобы избежать циклических импортов
        from .models import db, Photo
        
        try:
            with Image.open(orig_path) as img:
                img = ImageOps.exif_transpose(img)
                
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Medium image (optimized_path in DB) - 1200px for lightbox initial load
                medium_img = img.copy()
                medium_img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                medium_img.save(opt_path, 'WEBP', quality=90)

                # Thumbnail (thumbnail_path in DB) - 400px for grid
                thumb_img = img.copy()
                thumb_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                thumb_img.save(thumb_path, 'WEBP', quality=85)
            
            # Обновляем статус фото в БД
            photo = Photo.query.get(photo_id)
            if photo:
                photo.status = 'ready'
                db.session.commit()
                
        except Exception as e:
            print(f"Error processing image {photo_id}: {e}")
            # Можно установить статус 'error' если нужно