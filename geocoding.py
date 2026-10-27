"""Adresleri koordinata (enlem, boylam) çeviren modül.

OpenStreetMap'in ücretsiz Nominatim servisini kullanır. Servisin kullanım
kurallarına uyarız:
  1. Her istekte bizi tanıtan bir User-Agent gönderilir.
  2. Saniyede en fazla 1 istek atılır.
  3. Aynı adres tekrar sorulmaz; sonuçlar önbellekte (bellek + JSON dosyası) tutulur.
"""

import json
import os
import threading
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "teslimat-rota-planlayici/1.0 (github.com/baduone03/teslimat-rota-planlayici)"
MIN_BEKLEME_SN = 1.0  # Nominatim kuralı: saniyede en fazla 1 istek

ONBELLEK_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "veri", "geocode_onbellek.json")

_onbellek = None  # {normalize_adres: {"enlem":..., "boylam":..., "bulunan_adres":...} veya None}
_son_istek_zamani = 0.0
_kilit = threading.Lock()


def _normalize(adres):
    """'  Atakum,  Samsun ' ile 'atakum, samsun' aynı anahtar olsun diye."""
    return " ".join(adres.lower().split())


def _onbellegi_yukle():
    global _onbellek
    if _onbellek is None:
        try:
            with open(ONBELLEK_DOSYASI, encoding="utf-8") as f:
                _onbellek = json.load(f)
        except (OSError, ValueError):
            _onbellek = {}
    return _onbellek


def _onbellegi_kaydet():
    try:
        os.makedirs(os.path.dirname(ONBELLEK_DOSYASI), exist_ok=True)
        with open(ONBELLEK_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(_onbellek, f, ensure_ascii=False, indent=1)
    except OSError:
        pass  # Dosyaya yazılamazsa bellek önbelleği yine çalışır.


def _hiz_sinirina_uy():
    """Son istekten bu yana 1 saniye geçmediyse aradaki farkı bekler."""
    global _son_istek_zamani
    gecen = time.monotonic() - _son_istek_zamani
    if gecen < MIN_BEKLEME_SN:
        time.sleep(MIN_BEKLEME_SN - gecen)
    _son_istek_zamani = time.monotonic()


def adres_koordinat(adres, zaman_asimi=10):
    """Tek bir adresi koordinata çevirir.

    Dönüş: {"enlem": float, "boylam": float, "bulunan_adres": str}
           Adres bulunamazsa None.
    Ağ hatasında istisna (requests.RequestException) fırlatır; çağıran karar verir.
    """
    anahtar = _normalize(adres)
    with _kilit:
        onbellek = _onbellegi_yukle()
        if anahtar in onbellek:
            return onbellek[anahtar]

        _hiz_sinirina_uy()
        yanit = requests.get(
            NOMINATIM_URL,
            params={
                "q": adres,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "tr",
                "accept-language": "tr",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=zaman_asimi,
        )
        yanit.raise_for_status()
        sonuclar = yanit.json()

        if sonuclar:
            ilk = sonuclar[0]
            sonuc = {
                "enlem": float(ilk["lat"]),
                "boylam": float(ilk["lon"]),
                "bulunan_adres": ilk.get("display_name", adres),
            }
        else:
            sonuc = None

        onbellek[anahtar] = sonuc
        _onbellegi_kaydet()
        return sonuc


def toplu_koordinat(adresler, yedek_koordinatlar=None, ilerleme=None):
    """Birden fazla adresi sırayla koordinata çevirir.

    yedek_koordinatlar: {adres: (enlem, boylam)} — servise ulaşılamazsa kullanılır.
    ilerleme: her adresten sonra ilerleme(i, toplam, adres) şeklinde çağrılan fonksiyon.

    Dönüş: her adres için {"adres", "enlem", "boylam", "bulunan_adres", "kaynak"} sözlüğü.
           "kaynak" = "nominatim", "yedek" veya "bulunamadi".
    """
    yedek_koordinatlar = yedek_koordinatlar or {}
    sonuclar = []
    for i, adres in enumerate(adresler):
        try:
            bulunan = adres_koordinat(adres)
            kaynak = "nominatim" if bulunan else "bulunamadi"
        except requests.RequestException:
            bulunan, kaynak = None, "bulunamadi"

        if bulunan is None and adres in yedek_koordinatlar:
            enlem, boylam = yedek_koordinatlar[adres]
            bulunan = {"enlem": enlem, "boylam": boylam, "bulunan_adres": adres + " (yaklaşık)"}
            kaynak = "yedek"

        sonuclar.append({"adres": adres, **(bulunan or {"enlem": None, "boylam": None, "bulunan_adres": None}), "kaynak": kaynak})
        if ilerleme:
            ilerleme(i + 1, len(adresler), adres)
    return sonuclar
