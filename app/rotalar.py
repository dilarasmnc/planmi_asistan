import logging
import re

from flask import Blueprint, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.database import DatabaseError, musteri_adayi_ekle, tum_adaylari_getir
from app.services.yapay_zeka_servisi import (
    YapayZekaServisHatasi,
    yapay_zeka_servisi,
)

logger = logging.getLogger(__name__)

# İki blueprint: sayfalar (/ ve /dashboard) ve API (/api/...)
sayfalar_bp = Blueprint("sayfalar", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")

# Basit e-posta kontrolü: bir @ ve noktalı alan adı
EPOSTA_DESENI = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# NVARCHAR(n) uzunluğunu SQLite zorlamaz, bu yüzden burada biz kontrol ediyoruz
SINIRLAR = {"ad_soyad": 100, "eposta": 150, "telefon": 30, "not": 1000}
MESAJ_SINIRI = 1000


def _hata(mesaj, kod):
    """Her hata cevabı aynı biçimde döner: {basari: False, hata: ...}"""
    return jsonify({"basari": False, "hata": mesaj}), kod


# ---------- SAYFALAR ----------

@sayfalar_bp.route("/")
def ana_sayfa():
    return render_template("index.html")


@sayfalar_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@sayfalar_bp.route("/health")
def saglik():
    # Render ve biz "servis ayakta mı" diye buraya bakarız
    return jsonify({"basari": True, "durum": "ok"})


# ---------- API: SOHBET ----------

@api_bp.route("/sohbet", methods=["POST"])
def sohbet():
    veri = request.get_json(silent=True)  # bozuk JSON'da hata fırlatmaz, None döner
    if not isinstance(veri, dict):
        return _hata("Geçersiz istek.", 400)

    mesaj = veri.get("mesaj")
    if not isinstance(mesaj, str) or not mesaj.strip():
        return _hata("Lütfen bir mesaj yazın.", 400)
    if len(mesaj) > MESAJ_SINIRI:
        return _hata("Mesaj çok uzun.", 400)

    gecmis = veri.get("gecmis")
    if not isinstance(gecmis, list):
        gecmis = []

    try:
        cevap = yapay_zeka_servisi.yanit_uret(mesaj.strip(), gecmis)
    except YapayZekaServisHatasi as e:
        # Servis zaten kullanıcıya uygun, genel bir mesaj üretti
        return _hata(str(e), 503)

    return jsonify({"basari": True, "cevap": cevap})


# ---------- API: DEMO TALEPLERİ (ADAYLAR) ----------

def _adayi_dogrula(veri):
    """Hata varsa metnini, yoksa None döner."""
    for alan in ("ad_soyad", "eposta"):
        deger = veri.get(alan)
        if not isinstance(deger, str) or not deger.strip():
            return "Ad soyad ve e-posta zorunludur."

    for alan, sinir in SINIRLAR.items():
        deger = veri.get(alan)
        if deger is not None and (not isinstance(deger, str) or len(deger) > sinir):
            return f"'{alan}' alanı geçersiz veya çok uzun."

    if not EPOSTA_DESENI.match(veri["eposta"].strip()):
        return "Geçerli bir e-posta adresi girin."

    if veri.get("kvkk_onay") is not True:
        return "KVKK onayı zorunludur."

    return None


@api_bp.route("/adaylar", methods=["POST"])
def aday_ekle():
    veri = request.get_json(silent=True)
    if not isinstance(veri, dict):
        return _hata("Geçersiz istek.", 400)

    hata = _adayi_dogrula(veri)
    if hata:
        return _hata(hata, 400)

    try:
        yeni_id = musteri_adayi_ekle(
            ad_soyad=veri["ad_soyad"].strip(),
            eposta=veri["eposta"].strip(),
            telefon=(veri.get("telefon") or "").strip() or None,
            not_metni=(veri.get("not") or "").strip() or None,  # JSON'da "not", DB'de "not_metni"
        )
    except DatabaseError:
        return _hata("Kayıt şu an alınamadı, lütfen tekrar deneyin.", 500)

    return jsonify({"basari": True, "id": yeni_id}), 201


@api_bp.route("/adaylar", methods=["GET"])
def adaylari_listele():
    try:
        adaylar = tum_adaylari_getir()
    except DatabaseError:
        return _hata("Kayıtlar şu an getirilemedi.", 500)

    return jsonify({"basari": True, "adaylar": adaylar})


# ---------- SON ÇARE HATA YAKALAYICI ----------

@api_bp.app_errorhandler(Exception)
def beklenmeyen_hata(e):
    # 404, 405 gibi normal HTTP hatalarını bozma
    if isinstance(e, HTTPException):
        if request.path.startswith("/api"):
            return _hata(e.description, e.code)
        return e
    # Beklenmeyen hata: ayrıntı sadece log'a, kullanıcıya genel mesaj
    logger.exception("Beklenmeyen hata: %s", request.path)
    return _hata("Beklenmeyen bir hata oluştu.", 500)