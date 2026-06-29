import os
import shutil
import zipfile
import io
from flask import Blueprint, render_template, request, redirect, url_for, abort, current_app, jsonify, session, make_response, send_file
from .models import db, Album, Photo
from .image_utils import process_and_save_image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

main = Blueprint('main', __name__)

@main.route('/')
def explore():
    is_admin = session.get('is_admin', False)
    albums = Album.query.order_by(Album.created_at.desc()).all()
    
    # Attach cover image manually for faster rendering or use relations
    for album in albums:
        album.cover = next((p for p in album.photos if p.is_cover), album.photos[0] if album.photos else None)

    return render_template('explore.html', albums=albums, is_admin=is_admin)

@main.route('/admin/<secret_key>')
def admin_login(secret_key):
    if secret_key == current_app.config.get('ADMIN_SECRET'):
        session['is_admin'] = True
        return redirect(url_for('main.explore'))
    abort(404)

@main.route('/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('main.explore'))

@main.route('/album/<token>')
def view_album(token):
    album = Album.query.filter_by(token=token).first_or_404()
    page = request.args.get('page', 1, type=int)
    
    # Add simple pagination (50 photos per page)
    pagination = Photo.query.filter_by(album_id=album.id).order_by(Photo.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    photos = pagination.items
    
    # We still need a cover for the hero section
    first_photo = Photo.query.filter_by(album_id=album.id).order_by(Photo.created_at.desc()).first()
    cover = next((p for p in photos if p.is_cover), first_photo)
    
    is_admin = session.get('is_admin', False)
    return render_template('album.html', album=album, photos=photos, pagination=pagination, cover=cover, is_admin=is_admin)

@main.route('/album/<token>/photos_partial')
def photos_partial(token):
    album = Album.query.filter_by(token=token).first_or_404()
    page = request.args.get('page', 1, type=int)
    
    pagination = Photo.query.filter_by(album_id=album.id).order_by(Photo.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    photos = pagination.items
    
    is_admin = session.get('is_admin', False)
    html = render_template('partials/photo_grid.html', photos=photos, is_admin=is_admin)
    resp = make_response(html)
    resp.headers['X-Has-Next'] = 'true' if pagination.has_next else 'false'
    return resp

@main.route('/set_cover/<int:album_id>/<int:photo_id>', methods=['POST'])
def set_cover(album_id, photo_id):
    if not session.get('is_admin'):
        abort(403)
        
    album = Album.query.get_or_404(album_id)
    photo = Photo.query.get_or_404(photo_id)
    
    if photo.album_id != album.id:
        abort(400)
        
    # Reset all covers in album
    Photo.query.filter_by(album_id=album.id).update({'is_cover': False})
    # Set new cover
    photo.is_cover = True
    db.session.commit()
    
    return redirect(url_for('main.view_album', token=album.token))

@main.route('/album/<token>/download_all')
def download_all(token):
    album = Album.query.filter_by(token=token).first_or_404()
    photos = Photo.query.filter_by(album_id=album.id).all()
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for photo in photos:
            photo_path = os.path.join(current_app.root_path, 'static', photo.original_path)
            if os.path.exists(photo_path):
                arcname = os.path.basename(photo_path)
                zf.write(photo_path, arcname)
                
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{album.title or 'album'}_photos.zip"
    )

@main.route('/create_album', methods=['GET', 'POST'])
def create_album():
    if not session.get('is_admin'):
        abort(403)
        
    if request.method == 'POST':
        # AJAX form submission for album creation
        title = request.form.get('title')
        description = request.form.get('description', '')
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400

        new_album = Album(title=title, description=description)
        db.session.add(new_album)
        db.session.commit()
        
        return jsonify({
            'album_id': new_album.id, 
            'token': new_album.token,
            'redirect_url': url_for('main.view_album', token=new_album.token)
        })

    return render_template('upload.html')

@main.route('/edit_album/<int:album_id>')
def edit_album(album_id):
    if not session.get('is_admin'):
        abort(403)
    album = Album.query.get_or_404(album_id)
    return render_template('edit_album.html', album=album)

@main.route('/upload_photo/<int:album_id>', methods=['POST'])
def upload_photo(album_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    album = Album.query.get_or_404(album_id)
    file = request.files.get('file')
    is_cover = request.form.get('is_cover') == 'true'
    
    if not file or file.filename == '':
        return jsonify({'error': 'No file provided'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
        
    orig, opt, thumb, img_width, img_height = process_and_save_image(file, album.id)

    new_photo = Photo(
        album_id=album.id,
        original_path=f"uploads/{album.id}/{orig}",
        optimized_path=f"uploads/{album.id}/{opt}",
        thumbnail_path=f"uploads/{album.id}/{thumb}",
        is_cover=is_cover,
        img_width=img_width,
        img_height=img_height,
    )
    db.session.add(new_photo)
    db.session.commit()
    
    return jsonify({'success': True, 'photo_id': new_photo.id})

@main.route('/delete_photo/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    photo = Photo.query.get_or_404(photo_id)
    
    # Delete files from disk
    for path_attr in ['original_path', 'optimized_path', 'thumbnail_path']:
        full_path = os.path.join(current_app.root_path, 'static', getattr(photo, path_attr))
        if os.path.exists(full_path):
            os.remove(full_path)
            
    db.session.delete(photo)
    db.session.commit()
    
    return jsonify({'success': True})

@main.route('/delete_album/<int:album_id>', methods=['POST'])
def delete_album(album_id):
    if not session.get('is_admin'):
        abort(403)
        
    album = Album.query.get_or_404(album_id)
    
    # Delete folder from disk
    album_folder = os.path.join(current_app.root_path, 'static', 'uploads', str(album.id))
    if os.path.exists(album_folder):
        shutil.rmtree(album_folder)
        
    db.session.delete(album)
    db.session.commit()
    
    return redirect(url_for('main.explore'))