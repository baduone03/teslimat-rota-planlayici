from unittest import mock

import pytest
import requests

import geocoding


@pytest.fixture(autouse=True)
def temiz_onbellek(tmp_path, monkeypatch):
    """Her test boş bir önbellekle ve geçici bir dosyayla başlasın."""
    monkeypatch.setattr(geocoding, "_onbellek", None)
    monkeypatch.setattr(geocoding, "ONBELLEK_DOSYASI", str(tmp_path / "onbellek.json"))
    monkeypatch.setattr(geocoding, "_son_istek_zamani", 0.0)


def _sahte_yanit(veri):
    yanit = mock.Mock()
    yanit.json.return_value = veri
    yanit.raise_for_status.return_value = None
    return yanit


def test_adres_koordinata_cevrilir_ve_user_agent_gonderilir():
    veri = [{"lat": "41.29", "lon": "36.33", "display_name": "İlkadım, Samsun"}]
    with mock.patch("geocoding.requests.get", return_value=_sahte_yanit(veri)) as get:
        sonuc = geocoding.adres_koordinat("İlkadım, Samsun")

    assert sonuc == {"enlem": 41.29, "boylam": 36.33, "bulunan_adres": "İlkadım, Samsun"}
    assert "User-Agent" in get.call_args.kwargs["headers"]


def test_ayni_adres_ikinci_kez_sorulunca_aga_gidilmez():
    veri = [{"lat": "41.29", "lon": "36.33", "display_name": "x"}]
    with mock.patch("geocoding.requests.get", return_value=_sahte_yanit(veri)) as get:
        geocoding.adres_koordinat("Atakum, Samsun")
        geocoding.adres_koordinat("  atakum,   SAMSUN ")
    assert get.call_count == 1


def test_istekler_arasinda_en_az_1_saniye_beklenir():
    veri = [{"lat": "41", "lon": "36", "display_name": "x"}]
    with mock.patch("geocoding.requests.get", return_value=_sahte_yanit(veri)), \
         mock.patch("geocoding.time.sleep") as uyu:
        geocoding.adres_koordinat("Adres A")
        geocoding.adres_koordinat("Adres B")
    # İkinci istek ilkinden hemen sonra geldiği için beklemiş olmalı.
    assert uyu.called
    assert uyu.call_args.args[0] > 0.9


def test_bulunamayan_adres_none_doner():
    with mock.patch("geocoding.requests.get", return_value=_sahte_yanit([])):
        assert geocoding.adres_koordinat("olmayan yer xyz") is None


def test_ag_hatasinda_yedek_koordinat_kullanilir():
    with mock.patch("geocoding.requests.get", side_effect=requests.ConnectionError):
        sonuclar = geocoding.toplu_koordinat(["Depo"], yedek_koordinatlar={"Depo": (41.0, 36.0)})
    assert sonuclar[0]["kaynak"] == "yedek"
    assert (sonuclar[0]["enlem"], sonuclar[0]["boylam"]) == (41.0, 36.0)
