import sqlite3
import logging
from config import Config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Veritabanı işlemi başarısız olduğunda fırlatılır."""

def get_db():
    conn = sqlite3.connect(Config.DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(app):
    conn = None
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaylar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_soyad         NVARCHAR(100) NOT NULL,
                eposta           NVARCHAR(150) NOT NULL,
                telefon          NVARCHAR(30),
                not_metni        NVARCHAR(1000),
                durum            NVARCHAR(20) NOT NULL DEFAULT 'Yeni',
                olusturma_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except sqlite3.Error as e:
        logger.error("Tablo oluşturulamadı: %s", e)
        raise DatabaseError("Veritabanı hazırlanamadı.") from e
    finally:
        if conn is not None:
            conn.close()

def musteri_adayi_ekle(ad_soyad, eposta, telefon=None, not_metni=None):
    conn = None
    try:
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO adaylar (ad_soyad, eposta, telefon, not_metni) "
            "VALUES (?, ?, ?, ?)",
            (ad_soyad, eposta, telefon, not_metni),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error("Kayıt eklenemedi: %s", e)
        raise DatabaseError("Kayıt eklenemedi.") from e
    finally:
        if conn is not None:
            conn.close()

def tum_adaylari_getir():
    conn = None
    try:
        conn = get_db()
        satirlar = conn.execute(
            "SELECT id, ad_soyad, eposta, telefon, not_metni, durum, "
            "olusturma_tarihi FROM adaylar ORDER BY id DESC"
        ).fetchall()
        return [dict(satir) for satir in satirlar]
    except sqlite3.Error as e:
        logger.error("Kayıtlar okunamadı: %s", e)
        raise DatabaseError("Kayıtlar okunamadı.") from e
    finally:
        if conn is not None:
            conn.close()