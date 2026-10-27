"""Uygulamanın uçtan uca testleri: Streamlit'in AppTest aracıyla tarayıcısız çalıştırılır.
Ağ çağrıları taklit edilir (OSRM'e ulaşılamıyor gibi), böylece testler her ortamda aynı sonucu verir."""

import os
from unittest import mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


@pytest.fixture
def uygulama():
    with mock.patch("mesafe.requests.get", side_effect=requests.ConnectionError), \
         mock.patch("geocoding.requests.get", side_effect=requests.ConnectionError):
        at = AppTest.from_file(APP, default_timeout=60)
        at.run()
        yield at


def _hesapla(at):
    at.button[0].click().run()
    assert not at.exception, at.exception


def _uyarilar(at):
    return [u.value for u in at.warning]


def test_ornek_verilerle_hesaplanir_ve_supheli_konum_yok(uygulama):
    _hesapla(uygulama)
    assert any("Girilen sırayla gitseydin" in b.value and "sefer" in b.value for b in uygulama.success)
    assert not any("yanlış olabilir" in u for u in _uyarilar(uygulama))
    assert not any("Girdileri değiştirdiniz" in u for u in _uyarilar(uygulama))


def test_girdi_degisince_eski_sonuc_uyarisi(uygulama):
    _hesapla(uygulama)
    uygulama.number_input[0].set_value(900).run()  # kapasite değişti, butona basılmadı
    assert any("Girdileri değiştirdiniz" in u for u in _uyarilar(uygulama))
    _hesapla(uygulama)
    assert not any("Girdileri değiştirdiniz" in u for u in _uyarilar(uygulama))


def test_ters_yazilmis_depo_koordinati_uyarilir(uygulama):
    uygulama.text_input[0].set_value("Depo (36.3540910, 41.2767769)").run()  # enlem/boylam ters
    _hesapla(uygulama)
    uyari = next(u for u in _uyarilar(uygulama) if "yanlış olabilir" in u)
    assert "DEPO" in uyari and "ters yazılmış olabilir" in uyari


def test_turkiye_disi_koordinat_uyarilir(uygulama):
    uygulama.text_input[0].set_value("Paris (48.8566, 2.3522)").run()
    _hesapla(uygulama)
    assert any("Türkiye sınırları dışında" in u for u in _uyarilar(uygulama))


def _hatalar(at):
    return [h.value for h in at.error]


def test_bos_depo_reddedilir(uygulama):
    uygulama.text_input[0].set_value("").run()
    _hesapla(uygulama)
    assert any("Depo adresi boş olamaz" in h for h in _hatalar(uygulama))


def test_bulunamayan_depo_hata_verir(uygulama):
    uygulama.text_input[0].set_value("Hiç olmayan bir yer xyz").run()  # ağ kapalı → bulunamaz
    _hesapla(uygulama)
    assert any("Depo adresi bulunamadı" in h for h in _hatalar(uygulama))


def test_tek_araca_sigmayan_yuk_reddedilir(uygulama):
    uygulama.number_input[0].set_value(200).run()  # kapasite 200 kg; 300 kg'lık durak var
    _hesapla(uygulama)
    assert any("tek bir aracın kapasitesinden" in h for h in _hatalar(uygulama))


def test_arac_sayisi_yetmezse_reddedilir(uygulama):
    uygulama.number_input[1].set_value(1).run()  # 1380 kg, 1 x 800 kg araç
    _hesapla(uygulama)
    assert any("en az **2 araç**" in h for h in _hatalar(uygulama))
