"""Canlı sistem duman testleri: GERÇEK internete çıkar, ağ çağrıları taklit EDİLMEZ.

GitHub Actions her gün çalıştırır (.github/workflows/canli-kontrol.yml). Amaç:
  - Ücretsiz servislerden (Nominatim, Photon, OSRM) biri bozulursa haber almak,
  - Yayındaki uygulamanın açılıp örnek verilerle hesap yapabildiğini doğrulamak,
  - Yan etki: uygulamayı her gün ziyaret ederek uyku moduna girmesini önlemek.

Yerelde: CANLI_URL=http://localhost:8501 pytest tests_canli -v
"""

import os
import time

import pytest
from playwright.sync_api import sync_playwright

import geocoding
import mesafe

CANLI_URL = os.environ.get("CANLI_URL", "https://teslimat-rota-planlayici.streamlit.app")
CHROMIUM_YOLU = os.environ.get("CHROMIUM_YOLU")  # boşsa Playwright'ın kendi tarayıcısı kullanılır
EKRAN_GORUNTUSU = os.environ.get("EKRAN_GORUNTUSU", "canli_kontrol.png")
SAMSUN_MERKEZ = (41.29, 36.33)


@pytest.mark.parametrize("servis", [geocoding._nominatim, geocoding._photon], ids=["nominatim", "photon"])
def test_konum_servisi_cevap_veriyor(servis):
    sonuc = servis("Atakum, Samsun", 30)
    assert sonuc is not None, "servis 'Atakum, Samsun' adresini bulamadı"
    assert mesafe.haversine_km((sonuc["enlem"], sonuc["boylam"]), SAMSUN_MERKEZ) < 30


def test_osrm_gercek_yol_mesafesi_veriyor():
    sonuc = mesafe.mesafe_matrisi([(41.2768, 36.3541), (41.3615, 36.2339)])
    assert sonuc["kaynak"] == "osrm", "OSRM'e ulaşılamadı, uygulama tahmini mesafeye düşerdi"
    assert 10 < sonuc["mesafe_km"][0][1] < 40


def _uygulama_cercevesi(sayfa, zaman_asimi_sn=240):
    """Streamlit Cloud uygulamayı bir iframe içinde açabilir ve uyuyorsa önce uyandırmak gerekir."""
    bitis = time.time() + zaman_asimi_sn
    while time.time() < bitis:
        uyandir = sayfa.get_by_role("button", name="Yes, get this app back up!")
        if uyandir.count() and uyandir.first.is_visible():
            uyandir.first.click()
        for cerceve in sayfa.frames:
            buton = cerceve.get_by_role("button", name="Rotayı Hesapla")
            if buton.count() and buton.first.is_visible():
                return cerceve
        time.sleep(3)
    raise AssertionError(f"Uygulama {zaman_asimi_sn} sn içinde açılmadı: {CANLI_URL}")


def test_canli_uygulama_ornek_verilerle_hesaplar():
    with sync_playwright() as p:
        tarayici = p.chromium.launch(executable_path=CHROMIUM_YOLU) if CHROMIUM_YOLU else p.chromium.launch()
        sayfa = tarayici.new_page(viewport={"width": 1400, "height": 1000})
        try:
            sayfa.goto(CANLI_URL, timeout=120_000)
            cerceve = _uygulama_cercevesi(sayfa)
            cerceve.get_by_role("button", name="Rotayı Hesapla").first.click()
            sonuc = cerceve.locator('[data-testid="stAlertContentSuccess"]')
            sonuc.wait_for(timeout=120_000)
            time.sleep(2)  # uyarılar da yerleşsin

            metin = sonuc.inner_text()
            uyarilar = cerceve.locator('[data-testid="stAlertContentWarning"]').all_inner_texts()
            hatalar = cerceve.locator('[data-testid="stAlertContentError"]').all_inner_texts()
            assert "Girilen sırayla gitseydin" in metin
            assert not hatalar, f"Uygulama hata gösterdi: {hatalar}"
            assert not uyarilar, f"Örnek verilerde uyarı çıkmamalı (servis sorunu olabilir): {uyarilar}"
        finally:
            sayfa.screenshot(path=EKRAN_GORUNTUSU, full_page=True)
            tarayici.close()
