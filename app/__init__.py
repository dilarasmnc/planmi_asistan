import logging
import os

from flask import Flask
from flask_cors import CORS

from config import config
from app.database import init_db


def create_app(config_name=None):
    """Uygulama fabrikası: uygulamayı kurar ve hazır halde döndürür."""
    # Hangi ayar? APP_ENV=production ise ProductionConfig, yoksa varsayılan
    config_name = config_name or os.environ.get("APP_ENV", "default")
    ayar = config.get(config_name, config["default"])

    app = Flask(__name__)
    app.config.from_object(ayar)

    # Log ayarı: Render'da hatalar buradan görünür
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # CORS: hangi sitelerin API'mize istek atabileceği (Wix sitesi)
    # .env'de virgülle ayrılmış liste olabilir; "*" herkese izin verir
    ham = app.config["CORS_ORIGINS"]
    izinli = "*" if ham.strip() == "*" else [o.strip() for o in ham.split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": izinli}})

    # Veritabanı tablosunu hazırla (yoksa oluşturur)
    with app.app_context():
        init_db(app)

    # Rotaları kaydet (en sonda import: dairesel import sorunu olmasın)
    from app.rotalar import api_bp, sayfalar_bp
    app.register_blueprint(sayfalar_bp)
    app.register_blueprint(api_bp)

    return app