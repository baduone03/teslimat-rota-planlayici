"""Adresleri koordinata (enlem, boylam) çeviren modül.

Ücretsiz ve API anahtarı istemeyen iki OpenStreetMap tabanlı servis kullanır:
  1. Nominatim (asıl servis)
  2. Photon (Nominatim bulamazsa veya cevap vermezse yedek)
Kullanıcı adres yerine doğrudan "41.2867, 36.33" gibi koordinat da yazabilir, ya da okunur bir isimle
"Kurupelit, Atakum (41.364, 36.22)"; bu durumda hiçbir servise gidilmez.

Servislerin kullanım kurallarına uyarız:
  1. Her istekte bizi tanıtan bir User-Agent gönderilir.
  2. Saniyede en fazla 1 istek atılır; "yoğunum" (429) cevabında bekleyip tekrar denenir.
  3. Aynı adres tekrar sorulmaz; sonuçlar önbellekte (bellek + JSON dosyası) tutulur.
"""

import json
import os
import re
import threading
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "teslimat-rota-planlayici/1.0 (github.com/baduone03/teslimat-rota-planlayici)"
MIN_BEKLEME_SN = 1.0  # Nominatim kuralı: saniyede en fazla 1 istek
TEKRAR_DENEME = 2  # 429/5xx cevabında kaç kez daha denensin
TURKIYE_SINIRLARI = (25.6, 35.8, 44.9, 42.2)  # min boylam, min enlem, maks boylam, maks enlem

ONBELLEK_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "veri", "geocode_onbellek.json")

# Desteklenen koordinat biçimleri (tek başına ya da "İsim (koordinat)" olarak):
#   41.2867, 36.33  |  41.2867 36.33  |  41,2867, 36,33 (virgüllü ondalık)  |  41°21'36.3"N 36°14'00.5"E
_NOKTALI_CIFT = re.compile(r"(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)")
_VIRGULLU_CIFT = re.compile(r"(-?\d{1,2},\d+)\s*[;\s]\s*(-?\d{1,3},\d+)|(-?\d{1,2},\d+)\s*,\s+(-?\d{1,3},\d+)")
_DMS = r"(\d{1,3})\s*°\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*['′’]\s*)?(?:(\d{1,2}(?:[.,]\d+)?)\s*(?:\"|″|”|'')\s*)?"
_DMS_CIFT = re.compile(rf"{_DMS}([NSKG])\s*,?\s*{_DMS}([EWDB])", re.IGNORECASE)
# Telefondan kopyalanan metinlerde gelebilen görünmez yön işaretleri vb.
GORUNMEZ_KARAKTERLER = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

_onbellek = None  # {normalize_adres: {"enlem", "boylam", "bulunan_adres", "kaynak"} veya None}
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


def _istek(url, params, zaman_asimi):
    """Hız sınırına uyarak GET isteği atar; 429/5xx cevabında 2 sn, 4 sn bekleyip tekrar dener."""
    for deneme in range(TEKRAR_DENEME + 1):
        _hiz_sinirina_uy()
        yanit = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=zaman_asimi)
        if yanit.status_code in (429, 502, 503, 504) and deneme < TEKRAR_DENEME:
            time.sleep(2 ** (deneme + 1))
            continue
        yanit.raise_for_status()
        return yanit.json()


def _derece(d, dk, sn, yon):
    deger = float(d) + float((dk or "0").replace(",", ".")) / 60 + float((sn or "0").replace(",", ".")) / 3600
    return -deger if yon.upper() in "SGWB" else deger  # güney/batı negatif


def _cift_coz(metin):
    """Yalnızca koordinattan oluşan bir metni (enlem, boylam) olarak döner; değilse None."""
    metin = metin.strip()
    if metin.startswith("(") and metin.endswith(")"):
        metin = metin[1:-1].strip()
    if m := _NOKTALI_CIFT.fullmatch(metin):
        return float(m.group(1)), float(m.group(2))
    if m := _VIRGULLU_CIFT.fullmatch(metin):
        enlem, boylam = (g for g in m.groups() if g)
        return float(enlem.replace(",", ".")), float(boylam.replace(",", "."))
    if m := _DMS_CIFT.fullmatch(metin):
        g = m.groups()
        return _derece(*g[0:4]), _derece(*g[4:8])
    return None


def koordinat_metni_coz(metin):
    """Metinde koordinat varsa (enlem, boylam, etiket) döner; yoksa None.

    '41.2867, 36.33'                    → (41.2867, 36.33, '41.2867, 36.33')
    'Kurupelit, Atakum (41.364, 36.22)' → (41.364, 36.22, 'Kurupelit, Atakum')
    Virgüllü ondalık ve dereceli (41°21'36.3"N 36°14'00.5"E) biçimler de tanınır.
    """
    metin = GORUNMEZ_KARAKTERLER.sub("", metin).replace("\u00a0", " ").strip()
    cift, etiket = _cift_coz(metin), None
    if cift is None and metin.endswith(")") and "(" in metin:
        acilis = metin.rindex("(")
        etiket = metin[:acilis].strip()
        cift = _cift_coz(metin[acilis + 1:-1]) if etiket else None
    if cift is None:
        return None
    enlem, boylam = cift
    if not (-90 <= enlem <= 90 and -180 <= boylam <= 180):
        return None
    return enlem, boylam, etiket or f"{enlem:.6f}, {boylam:.6f}"


def turkiye_icinde(enlem, boylam):
    """Kaba kontrol: nokta Türkiye'yi çevreleyen dikdörtgenin içinde mi?
    (Komşu ülkelerin bir kısmı da içeride kalır; ters yazımları ayrıca uzaklık kontrolü yakalar.)"""
    min_boylam, min_enlem, maks_boylam, maks_enlem = TURKIYE_SINIRLARI
    return min_enlem <= enlem <= maks_enlem and min_boylam <= boylam <= maks_boylam


def _nominatim(adres, zaman_asimi):
    sonuclar = _istek(NOMINATIM_URL, {
        "q": adres, "format": "jsonv2", "limit": 1, "countrycodes": "tr", "accept-language": "tr",
    }, zaman_asimi)
    if not sonuclar:
        return None
    ilk = sonuclar[0]
    return {"enlem": float(ilk["lat"]), "boylam": float(ilk["lon"]),
            "bulunan_adres": ilk.get("display_name", adres), "kaynak": "nominatim"}


def _photon(adres, zaman_asimi):
    veri = _istek(PHOTON_URL, {"q": adres, "limit": 1, "bbox": ",".join(map(str, TURKIYE_SINIRLARI))}, zaman_asimi)
    ozellikler = veri.get("features") or []
    if not ozellikler:
        return None
    boylam, enlem = ozellikler[0]["geometry"]["coordinates"]  # GeoJSON: [boylam, enlem]
    p = ozellikler[0].get("properties", {})
    parcalar = [p.get(k) for k in ("name", "street", "district", "city", "county", "state", "country")]
    bulunan = ", ".join(dict.fromkeys(x for x in parcalar if x)) or adres  # tekrarları at, sırayı koru
    return {"enlem": float(enlem), "boylam": float(boylam), "bulunan_adres": bulunan, "kaynak": "photon"}


def adres_koordinat(adres, zaman_asimi=10):
    """Tek bir adresi koordinata çevirir: önce Nominatim, bulamazsa Photon.

    Dönüş: {"enlem", "boylam", "bulunan_adres", "kaynak"}; adres bulunamazsa None.
    İki servise de ulaşılamazsa requests.RequestException fırlatır; çağıran karar verir.
    """
    koordinat = koordinat_metni_coz(adres)
    if koordinat:
        enlem, boylam, etiket = koordinat
        return {"enlem": enlem, "boylam": boylam, "bulunan_adres": etiket, "kaynak": "koordinat"}

    anahtar = _normalize(adres)
    with _kilit:
        onbellek = _onbellegi_yukle()
        if anahtar in onbellek:
            return onbellek[anahtar]

        sonuc, son_hata, hata_sayisi = None, None, 0
        for servis in (_nominatim, _photon):
            try:
                sonuc = servis(adres, zaman_asimi)
            except (requests.RequestException, ValueError, KeyError) as hata:
                son_hata, hata_sayisi = hata, hata_sayisi + 1
                continue
            if sonuc:
                break

        if sonuc is None and hata_sayisi == 2:
            raise requests.ConnectionError(f"Konum servislerine ulaşılamadı: {son_hata}")
        # "Bulunamadı" sonucunu yalnızca iki servis de gerçekten cevap verdiyse önbelleğe al.
        if sonuc is not None or hata_sayisi == 0:
            onbellek[anahtar] = sonuc
            _onbellegi_kaydet()
        return sonuc


def toplu_koordinat(adresler, ilerleme=None):
    """Birden fazla adresi sırayla koordinata çevirir.

    ilerleme: her adresten sonra ilerleme(i, toplam, adres) şeklinde çağrılan fonksiyon.

    Dönüş: her adres için {"adres", "enlem", "boylam", "bulunan_adres", "kaynak"} sözlüğü.
           "kaynak" = "nominatim", "photon", "koordinat" veya "bulunamadi".
    """
    sonuclar = []
    for i, adres in enumerate(adresler):
        try:
            bulunan = adres_koordinat(adres)
        except requests.RequestException:
            bulunan = None

        bos = {"enlem": None, "boylam": None, "bulunan_adres": None, "kaynak": "bulunamadi"}
        sonuclar.append({"adres": adres, **(bulunan or bos)})
        if ilerleme:
            ilerleme(i + 1, len(adresler), adres)
    return sonuclar
