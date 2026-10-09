import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

ISTEK_ZAMAN_ASIMI = 20     # saniye; bu sürede yanıt gelmezse vazgeç
GECMIS_SINIRI = 10         # modele en fazla kaç önceki mesaj gönderilsin
MESAJ_SINIRI = 1000        # tek bir mesajın en fazla karakter sayısı
MAKS_CEVAP_TOKEN = 800     # yanıtın en fazla uzunluğu


class YapayZekaServisHatasi(Exception):
    """Hiçbir yapay zekâ sağlayıcısından yanıt alınamadığında fırlatılır."""

class YapayZekaServisi:

    def yanit_uret(self, mesaj, gecmis=None):
        saglayicilar = self._saglayici_sirasi()
        if not saglayicilar:
            return self._demo_yaniti_ver()

        mesajlar = self._mesajlari_hazirla(mesaj, gecmis)

        for ad, cagir in saglayicilar:
            try:
                return cagir(mesajlar)
            except YapayZekaServisHatasi as e:
                logger.warning("%s başarısız oldu, sıradakine geçiliyor: %s", ad, e)

        raise YapayZekaServisHatasi("Şu an yanıt veremiyorum, lütfen tekrar dene.")

    def _saglayici_sirasi(self):
        secenekler = {
            "groq": (Config.GROQ_API_KEY, self._groq_cagir),
            "gemini": (Config.GEMINI_API_KEY, self._gemini_cagir),
        }
        birincil = (Config.AI_PROVIDER or "groq").lower()
        if birincil not in secenekler:
            birincil = "groq"

        sira = [birincil] + [ad for ad in secenekler if ad != birincil]
        return [(ad, secenekler[ad][1]) for ad in sira if secenekler[ad][0]]

    def _sistem_talimati_olustur(self):
        return Config.BUSINESS_CONTEXT.strip()

    def _mesajlari_hazirla(self, mesaj, gecmis):
        mesajlar = [{"role": "system", "content": self._sistem_talimati_olustur()}]

        if isinstance(gecmis, list):
            for kayit in gecmis[-GECMIS_SINIRI:]:
                if not isinstance(kayit, dict):
                    continue
                rol = kayit.get("rol")
                icerik = kayit.get("icerik")
                if rol in ("user", "assistant") and isinstance(icerik, str) and icerik.strip():
                    mesajlar.append({"role": rol, "content": icerik[:MESAJ_SINIRI]})

        mesajlar.append({"role": "user", "content": str(mesaj)[:MESAJ_SINIRI]})
        return mesajlar

    def _metni_dogrula(self, metin, kaynak):
        if not isinstance(metin, str) or not metin.strip():
            raise YapayZekaServisHatasi(f"{kaynak} boş yanıt döndürdü.")
        return metin.strip()

    def _groq_cagir(self, mesajlar):
        govde = {
            "model": Config.GROQ_MODEL,
            "messages": mesajlar,
            "max_completion_tokens": MAKS_CEVAP_TOKEN,
        }
        if "gpt-oss" in Config.GROQ_MODEL:
            govde["reasoning_effort"] = "low"
            govde["include_reasoning"] = False

        try:
            yanit = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                json=govde,
                timeout=ISTEK_ZAMAN_ASIMI,
            )
            if yanit.status_code != 200:
                raise YapayZekaServisHatasi(
                    f"Groq HTTP {yanit.status_code}: {yanit.text[:200]}"
                )
            metin = yanit.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            raise YapayZekaServisHatasi(f"Groq isteği başarısız: {e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise YapayZekaServisHatasi("Groq beklenmeyen biçimde yanıt verdi.") from e

        return self._metni_dogrula(metin, "Groq")

    def _gemini_cagir(self, mesajlar):
        sistem = mesajlar[0]["content"]
        icerikler = []
        for m in mesajlar[1:]:
            rol = "model" if m["role"] == "assistant" else "user"
            icerikler.append({"role": rol, "parts": [{"text": m["content"]}]})
        while icerikler and icerikler[0]["role"] == "model":
            icerikler.pop(0)

        govde = {
            "systemInstruction": {"parts": [{"text": sistem}]},
            "contents": icerikler,
            "generationConfig": {"maxOutputTokens": 1024},
        }
        adres = GEMINI_URL.format(model=Config.GEMINI_MODEL)

        try:
            yanit = requests.post(
                adres,
                headers={"x-goog-api-key": Config.GEMINI_API_KEY},
                json=govde,
                timeout=ISTEK_ZAMAN_ASIMI,
            )
            if yanit.status_code != 200:
                raise YapayZekaServisHatasi(
                    f"Gemini HTTP {yanit.status_code}: {yanit.text[:200]}"
                )
            parcalar = yanit.json()["candidates"][0]["content"]["parts"]
            metin = "".join(p.get("text", "") for p in parcalar)
        except requests.RequestException as e:
            raise YapayZekaServisHatasi(f"Gemini isteği başarısız: {e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise YapayZekaServisHatasi("Gemini beklenmeyen biçimde yanıt verdi.") from e

        return self._metni_dogrula(metin, "Gemini")

    def _demo_yaniti_ver(self):
        return (
            "Sistem şu an demo modunda çalışıyor. Yapay zekâ anahtarı "
            "tanımlı değil, lütfen .env dosyasını kontrol edin."
        )


yapay_zeka_servisi = YapayZekaServisi()