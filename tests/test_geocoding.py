from unittest import mock

import pytest
import requests

import geocoding


@pytest.fixture(autouse=True)
def temiz_onbellek(tmp_path, monkeypatch):
    """Her test boş bir önbellekle, geçici bir dosyayla ve beklemesiz başlasın."""
    monkeypatch.setattr(geocoding, "_onbellek", None)
    monkeypatch.setattr(geocoding, "ONBELLEK_DOSYASI", str(tmp_path / "onbellek.json"))
    monkeypatch.setattr(geocoding, "_son_istek_zamani", 0.0)


def _sahte_yanit(veri, durum=200):
    yanit = mock.Mock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    if durum >= 400:
        yanit.raise_for_status.side_effect = requests.HTTPError(str(durum))
    else:
        yanit.raise_for_status.return_value = None
    return yanit


def _servise_gore(nominatim, photon):
    """URL'ye bakıp Nominatim veya Photon için hazırlanan cevabı döndüren sahte requests.get."""
    def get(url, **kwargs):
        cevap = nominatim if "nominatim" in url else photon
        if isinstance(cevap, Exception):
            raise cevap
        return cevap
    return get


PHOTON_VERI = {"features": [{"geometry": {"coordinates": [36.33, 41.29]},
                             "properties": {"name": "İlkadım", "city": "Samsun", "country": "Türkiye"}}]}


def test_adres_koordinata_cevrilir_ve_user_agent_gonderilir():
    veri = [{"lat": "41.29", "lon": "36.33", "display_name": "İlkadım, Samsun"}]
    with mock.patch("geocoding.requests.get", return_value=_sahte_yanit(veri)) as get:
        sonuc = geocoding.adres_koordinat("İlkadım, Samsun")

    assert sonuc == {"enlem": 41.29, "boylam": 36.33, "bulunan_adres": "İlkadım, Samsun", "kaynak": "nominatim"}
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


def test_nominatim_bulamazsa_photon_denenir():
    sahte = _servise_gore(_sahte_yanit([]), _sahte_yanit(PHOTON_VERI))
    with mock.patch("geocoding.requests.get", side_effect=sahte):
        sonuc = geocoding.adres_koordinat("İlkadım, Samsun")
    assert sonuc["kaynak"] == "photon"
    assert (sonuc["enlem"], sonuc["boylam"]) == (41.29, 36.33)
    assert sonuc["bulunan_adres"] == "İlkadım, Samsun, Türkiye"


def test_nominatim_yogunsa_bekleyip_tekrar_dener():
    veri = [{"lat": "41", "lon": "36", "display_name": "x"}]
    cevaplar = [_sahte_yanit(None, 429), _sahte_yanit(veri)]
    with mock.patch("geocoding.requests.get", side_effect=cevaplar) as get, \
         mock.patch("geocoding.time.sleep"):
        sonuc = geocoding.adres_koordinat("Adres")
    assert sonuc["kaynak"] == "nominatim"
    assert get.call_count == 2


def test_iki_servis_de_bulamazsa_none_doner():
    sahte = _servise_gore(_sahte_yanit([]), _sahte_yanit({"features": []}))
    with mock.patch("geocoding.requests.get", side_effect=sahte):
        assert geocoding.adres_koordinat("olmayan yer xyz") is None


def test_koordinat_yazilirsa_servise_gidilmez():
    with mock.patch("geocoding.requests.get") as get:
        sonuc = geocoding.adres_koordinat("41.2867, 36.33")
    assert (sonuc["enlem"], sonuc["boylam"], sonuc["kaynak"]) == (41.2867, 36.33, "koordinat")
    assert not get.called
    assert geocoding.koordinat_metni_coz("41.2867 36.33") == (41.2867, 36.33, "41.286700, 36.330000")
    # Parantezli ve telefondan görünmez karakterle kopyalanmış hâller de tanınmalı
    assert geocoding.koordinat_metni_coz("(41.2767769, 36.3540910)")[:2] == (41.2767769, 36.354091)
    assert geocoding.koordinat_metni_coz("\u202a41.2767769,36.3540910\u202c")[:2] == (41.2767769, 36.354091)
    assert geocoding.koordinat_metni_coz("Atakum, Samsun") is None
    assert geocoding.koordinat_metni_coz("95, 36") is None  # geçersiz enlem


def test_isimli_koordinat_ismi_korur_ve_servise_gidilmez():
    with mock.patch("geocoding.requests.get") as get:
        sonuc = geocoding.adres_koordinat("Kurupelit, Atakum (41.3640, 36.2200)")
    assert (sonuc["enlem"], sonuc["boylam"]) == (41.364, 36.22)
    assert sonuc["bulunan_adres"] == "Kurupelit, Atakum"
    assert not get.called
    assert geocoding.koordinat_metni_coz("Depo (abc)") is None


def test_ag_hatasinda_adres_bulunamadi_olarak_isaretlenir():
    with mock.patch("geocoding.requests.get", side_effect=requests.ConnectionError):
        sonuclar = geocoding.toplu_koordinat(["Atakum, Samsun", "Depo (41.0, 36.0)"])
    assert sonuclar[0]["kaynak"] == "bulunamadi"
    # Koordinatlı giriş ağ olmasa da çalışır
    assert (sonuclar[1]["kaynak"], sonuclar[1]["enlem"]) == ("koordinat", 41.0)


@pytest.mark.parametrize("metin", [
    "41,2767769, 36,3540910",          # virgüllü ondalık
    "41,2767769 36,3540910",
    "41°16'36.4\"N 36°21'14.7\"E",    # Google Haritalar'ın dereceli biçimi
    "41°16′36.4″N, 36°21′14.7″E",
    "Depo (41°16'36.4\"N 36°21'14.7\"E)",
])
def test_virgullu_ve_dereceli_koordinatlar_taninir(metin):
    enlem, boylam, _ = geocoding.koordinat_metni_coz(metin)
    assert enlem == pytest.approx(41.27678, abs=1e-4)
    assert boylam == pytest.approx(36.35409, abs=1e-4)


def test_belirsiz_virgullu_metin_koordinat_sayilmaz():
    assert geocoding.koordinat_metni_coz("41,2, 36") is None


def test_turkiye_kaba_siniri():
    assert geocoding.turkiye_icinde(41.28, 36.35)       # Samsun
    assert not geocoding.turkiye_icinde(48.85, 2.35)    # Paris
