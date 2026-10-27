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

# "41.2867, 36.33", "41.2867 36.33" veya "Kurupelit, Atakum (41.364, 36.22)" (ondalık ayırıcı nokta)
_SAYI_CIFTI = r"(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)"
KOORDINAT_DESENI = re.compile(rf"^\s*\(?\s*{_SAYI_CIFTI}\s*\)?\s*$")  # parantezli de olabilir
# Telefondan kopyalanan metinlerde gelebilen görünmez yön işaretleri vb.
GORUNMEZ_KARAKTERLER = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
ETIKETLI_KOORDINAT_DESENI = re.compile(rf"^\s*(.+?)\s*\(\s*{_SAYI_CIFTI}\s*\)\s*$")

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


def koordinat_metni_coz(metin):
    """Metinde koordinat varsa (enlem, boylam, etiket) döner; yoksa None.

    '41.2867, 36.33'                 → (41.2867, 36.33, '41.2867, 36.33')
    'Kurupelit, Atakum (41.364, 36.22)' → (41.364, 36.22, 'Kurupelit, Atakum')
    """
    metin = GORUNMEZ_KARAKTERLER.sub("", metin).replace("\u00a0", " ")
    eslesme = KOORDINAT_DESENI.match(metin)
    if eslesme:
        etiket, enlem, boylam = f"{eslesme.group(1)}, {eslesme.group(2)}", eslesme.group(1), eslesme.group(2)
    else:
        eslesme = ETIKETLI_KOORDINAT_DESENI.match(metin)
        if not eslesme:
            return None
        etiket, enlem, boylam = eslesme.groups()
    enlem, boylam = float(enlem), float(boylam)
    if -90 <= enlem <= 90 and -180 <= boylam <= 180:
        return enlem, boylam, etiket
    return None


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


def toplu_koordinat(adresler, yedek_koordinatlar=None, ilerleme=None):
    """Birden fazla adresi sırayla koordinata çevirir.

    yedek_koordinatlar: {adres: (enlem, boylam)} — servisler bulamazsa/ulaşılamazsa kullanılır.
    ilerleme: her adresten sonra ilerleme(i, toplam, adres) şeklinde çağrılan fonksiyon.

    Dönüş: her adres için {"adres", "enlem", "boylam", "bulunan_adres", "kaynak"} sözlüğü.
           "kaynak" = "nominatim", "photon", "koordinat", "yedek" veya "bulunamadi".
    """
    yedek_koordinatlar = yedek_koordinatlar or {}
    sonuclar = []
    for i, adres in enumerate(adresler):
        try:
            bulunan = adres_koordinat(adres)
        except requests.RequestException:
            bulunan = None

        if bulunan is None and adres in yedek_koordinatlar:
            enlem, boylam = yedek_koordinatlar[adres]
            bulunan = {"enlem": enlem, "boylam": boylam, "bulunan_adres": adres + " (yaklaşık)", "kaynak": "yedek"}

        bos = {"enlem": None, "boylam": None, "bulunan_adres": None, "kaynak": "bulunamadi"}
        sonuclar.append({"adres": adres, **(bulunan or bos)})
        if ilerleme:
            ilerleme(i + 1, len(adresler), adres)
    return sonuclar
