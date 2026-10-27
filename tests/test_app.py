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
    uygulama.number_input[0].set_value(10).run()  # teslim süresi değişti, butona basılmadı
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


# Filo/kapasite hataları (en büyük araca sığmayan yük, toplam kapasite yetersiz) tablo düzenleyiciden
# girildiği için AppTest ile değiştirilemiyor; bu kurallar test_optimizasyon.py::test_filo_hatalari'nda sınanıyor.


def test_karisik_filo_ornekte_arac_adlari_gorunur(uygulama):
    _hesapla(uygulama)
    kutu = next(b.value for b in uygulama.success if "optimize plan" in b.value)
    assert "Kamyon" in kutu


def test_yukleme_plani_lifo_ve_fifo_ters_sirada(uygulama):
    _hesapla(uygulama)

    def ilk_yuklenen():
        tablo = next(d.value for d in uygulama.dataframe if "Yükleme sırası" in d.value.columns)
        return tablo.iloc[0]["Durak (teslim sırası)"]

    lifo = ilk_yuklenen()
    uygulama.radio[0].set_value("FIFO").run()
    fifo = ilk_yuklenen()
    assert fifo.startswith("1. ")          # FIFO: ilk teslim edilecek ilk yüklenir
    assert not lifo.startswith("1. ")      # LIFO: ilk yüklenen, son teslim edilecek olandır
    # Yükleme yöntemi rotayı değiştirmez → "girdiler değişti" uyarısı çıkmamalı
    assert not any("Girdileri değiştirdiniz" in u for u in _uyarilar(uygulama))
