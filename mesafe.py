"""Noktalar arası gerçek yol mesafesi/süresi ve haritada çizilecek rota.

Ücretsiz OSRM (Open Source Routing Machine) demo sunucusunu kullanır:
  - /table  : Tüm noktalar arasındaki mesafe ve süre matrisini TEK istekte verir.
  - /route  : Sıralı noktalardan geçen gerçek yol çizgisini verir (harita için).

OSRM'e ulaşılamazsa kuş uçuşu mesafe (Haversine) ile tahmini değer üretilir.
"""

import math

import requests

OSRM_URL = "https://router.project-osrm.org"
USER_AGENT = "teslimat-rota-planlayici/1.0 (github.com/baduone03/teslimat-rota-planlayici)"

# Tahmini mod katsayıları: yol, kuş uçuşundan ~%30 uzundur; şehir içi ort. hız ~40 km/sa.
YOL_KATSAYISI = 1.3
ORTALAMA_HIZ_KMSA = 40


def haversine_km(nokta1, nokta2):
    """İki (enlem, boylam) noktası arasındaki kuş uçuşu mesafe (km)."""
    enlem1, boylam1 = map(math.radians, nokta1)
    enlem2, boylam2 = map(math.radians, nokta2)
    d_enlem = enlem2 - enlem1
    d_boylam = boylam2 - boylam1
    a = math.sin(d_enlem / 2) ** 2 + math.cos(enlem1) * math.cos(enlem2) * math.sin(d_boylam / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _osrm_koordinat_metni(noktalar):
    # Dikkat: OSRM "boylam,enlem" sırası ister (enlem,boylam değil!).
    return ";".join(f"{boylam:.6f},{enlem:.6f}" for enlem, boylam in noktalar)


def tahmini_matris(noktalar):
    """İnternet yoksa: kuş uçuşu × yol katsayısı ile mesafe/süre matrisi."""
    n = len(noktalar)
    mesafe_km = [[0.0] * n for _ in range(n)]
    sure_dk = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                km = haversine_km(noktalar[i], noktalar[j]) * YOL_KATSAYISI
                mesafe_km[i][j] = km
                sure_dk[i][j] = km / ORTALAMA_HIZ_KMSA * 60
    return {"mesafe_km": mesafe_km, "sure_dk": sure_dk, "kaynak": "tahmini"}


def mesafe_matrisi(noktalar, zaman_asimi=20):
    """noktalar: [(enlem, boylam), ...]  (ilk nokta depo)

    Dönüş: {"mesafe_km": NxN liste, "sure_dk": NxN liste, "kaynak": "osrm" | "tahmini"}
    """
    try:
        yanit = requests.get(
            f"{OSRM_URL}/table/v1/driving/{_osrm_koordinat_metni(noktalar)}",
            params={"annotations": "distance,duration"},
            headers={"User-Agent": USER_AGENT},
            timeout=zaman_asimi,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        if veri.get("code") != "Ok":
            raise ValueError(veri.get("message", "OSRM hatası"))

        # Bir noktaya yol bulunamazsa OSRM null döner; bu durumda tahmini değere düşeriz.
        if any(d is None for satir in veri["distances"] for d in satir):
            raise ValueError("Bazı noktalar arasında yol bulunamadı")

        return {
            "mesafe_km": [[m / 1000 for m in satir] for satir in veri["distances"]],
            "sure_dk": [[s / 60 for s in satir] for satir in veri["durations"]],
            "kaynak": "osrm",
        }
    except (requests.RequestException, ValueError, KeyError):
        return tahmini_matris(noktalar)


def rota_geometrisi(sirali_noktalar, zaman_asimi=20):
    """Haritada çizmek için sıralı noktalardan geçen yol çizgisi.

    Dönüş: [(enlem, boylam), ...]. OSRM'e ulaşılamazsa noktaları düz çizgiyle birleştirir.
    """
    try:
        yanit = requests.get(
            f"{OSRM_URL}/route/v1/driving/{_osrm_koordinat_metni(sirali_noktalar)}",
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": USER_AGENT},
            timeout=zaman_asimi,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        if veri.get("code") != "Ok":
            raise ValueError(veri.get("message", "OSRM hatası"))
        # GeoJSON da [boylam, enlem] verir; folium için [enlem, boylam]'a çeviriyoruz.
        return [(enlem, boylam) for boylam, enlem in veri["routes"][0]["geometry"]["coordinates"]]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return list(sirali_noktalar)
