import os
from sqlalchemy import text
from flask import Flask
from .models import db
from .routes import main

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
    app.config['EXPLORE_SECRET'] = os.getenv('EXPLORE_SECRET', 'secret')
    app.config['ADMIN_SECRET'] = os.getenv('ADMIN_SECRET', 'admin-secret')

    db.init_app(app)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        # Безопасная миграция: добавляем новые колонки если их ещё нет
        with db.engine.connect() as conn:
            for col in ['img_width INTEGER', 'img_height INTEGER', 'status VARCHAR(20) DEFAULT \'ready\'', 'sort_order INTEGER DEFAULT 0']:
                try:
                    conn.execute(text(f'ALTER TABLE photo ADD COLUMN {col}'))
                    conn.commit()
                except Exception:
                    conn.rollback()  # Откатываем транзакцию, если колонка уже существует

    return app