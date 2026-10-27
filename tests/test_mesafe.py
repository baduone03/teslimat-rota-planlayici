from unittest import mock

import pytest
import requests

import mesafe


def test_haversine_bilinen_mesafe():
    # Ekvatorda 1 derece boylam ≈ 111.19 km
    assert mesafe.haversine_km((0, 0), (0, 1)) == pytest.approx(111.19, abs=0.1)
    assert mesafe.haversine_km((41.29, 36.33), (41.29, 36.33)) == 0


def test_osrm_yaniti_km_ve_dakikaya_cevrilir():
    sahte = mock.Mock()
    sahte.raise_for_status.return_value = None
    sahte.json.return_value = {
        "code": "Ok",
        "distances": [[0, 5000], [5200, 0]],  # metre
        "durations": [[0, 600], [660, 0]],  # saniye
    }
    with mock.patch("mesafe.requests.get", return_value=sahte) as get:
        sonuc = mesafe.mesafe_matrisi([(41.0, 36.0), (41.1, 36.1)])

    assert sonuc["kaynak"] == "osrm"
    assert sonuc["mesafe_km"] == [[0, 5.0], [5.2, 0]]
    assert sonuc["sure_dk"] == [[0, 10.0], [11.0, 0]]
    # OSRM boylam,enlem sırası ister
    assert "36.000000,41.000000;36.100000,41.100000" in get.call_args.args[0]


def test_osrm_ulasilamazsa_tahmini_matris_doner():
    with mock.patch("mesafe.requests.get", side_effect=requests.ConnectionError):
        sonuc = mesafe.mesafe_matrisi([(0, 0), (0, 1)])
    assert sonuc["kaynak"] == "tahmini"
    assert sonuc["mesafe_km"][0][1] == pytest.approx(111.19 * mesafe.YOL_KATSAYISI, abs=0.2)
    assert sonuc["mesafe_km"][0][0] == 0


def test_rota_geometrisi_hata_durumunda_duz_cizgi():
    noktalar = [(41.0, 36.0), (41.1, 36.1), (41.0, 36.0)]
    with mock.patch("mesafe.requests.get", side_effect=requests.Timeout):
        assert mesafe.rota_geometrisi(noktalar) == noktalar


SAMSUN = [(41.2768, 36.3541), (41.3615, 36.2339), (41.2263, 36.4526), (41.2950, 36.3314), (41.2656, 36.3373)]


def test_ters_yazilmis_koordinat_yakalanir():
    noktalar = SAMSUN + [(36.3314, 41.2950)]  # enlem ve boylam yer değiştirmiş (Suriye-Irak sınırı)
    supheliler = mesafe.supheli_uzak_noktalar(noktalar)
    assert [s["index"] for s in supheliler] == [5]
    assert supheliler[0]["ters_olabilir"] is True
    assert supheliler[0]["km"] > 500


def test_baska_sehre_dusen_adres_yakalanir_ama_ters_denmez():
    noktalar = SAMSUN + [(39.93, 32.85)]  # Ankara
    supheliler = mesafe.supheli_uzak_noktalar(noktalar)
    assert [s["index"] for s in supheliler] == [5]
    assert supheliler[0]["ters_olabilir"] is False


def test_normal_sehir_ici_noktalarda_uyari_yok():
    assert mesafe.supheli_uzak_noktalar(SAMSUN) == []
