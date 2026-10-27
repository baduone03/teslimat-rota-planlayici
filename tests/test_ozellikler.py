"""Özellik tabanlı testler (Hypothesis).

Tek tek örnek yazmak yerine Hypothesis yüzlerce rastgele senaryo üretir (rastgele konumlar, yükler,
kapasiteler) ve her birinde "hiçbir zaman bozulmaması gereken" kuralları kontrol eder.
Bir kural bozulursa Hypothesis senaryoyu küçülterek en basit karşı örneği raporlar.
"""

import itertools

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import geocoding
import mesafe
import optimizasyon

AYAR = settings(max_examples=30, deadline=None)  # çözücü her senaryoda ~0.2 sn çalışır
SURE = 0.2

# Samsun ve çevresinde rastgele bir nokta
samsun_noktasi = st.tuples(st.floats(41.15, 41.40), st.floats(36.15, 36.50))


@st.composite
def senaryo(draw, en_az=3, en_cok=8):
    """Depo + 2..7 durak, her durağa 0..400 kg, araç kapasitesi 400..1000 kg."""
    noktalar = draw(st.lists(samsun_noktasi, min_size=en_az, max_size=en_cok))
    talepler = [0] + draw(st.lists(st.integers(0, 400), min_size=len(noktalar) - 1, max_size=len(noktalar) - 1))
    kapasite = draw(st.integers(400, 1000))
    return mesafe.tahmini_matris(noktalar)["mesafe_km"], talepler, kapasite


def _gecerli_plan(rotalar, talepler, kapasite):
    duraklar = [d for r in rotalar for d in r[1:-1]]
    assert sorted(duraklar) == list(range(1, len(talepler))), "her durak tam bir kez ziyaret edilmeli"
    for r in rotalar:
        assert r[0] == 0 and r[-1] == 0, "her araç depodan çıkıp depoya dönmeli"
        assert sum(talepler[d] for d in r) <= kapasite, "araç kapasitesi aşılmamalı"


@AYAR
@given(senaryo(), st.booleans())
def test_plan_her_zaman_gecerli(s, araci_azalt):
    matris, talepler, kapasite = s
    arac_sayisi = len(talepler) - 1  # her durağa ayrı araç bile yetecek kadar: plan her zaman mümkün
    rotalar = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite, arac_sayisi, sure_limiti_sn=SURE,
                                              araci_azalt=araci_azalt)
    assert rotalar is not None
    assert len(rotalar) <= arac_sayisi
    _gecerli_plan(rotalar, talepler, kapasite)


@AYAR
@given(senaryo())
def test_optimize_plan_elle_plandan_uzun_olmaz(s):
    matris, talepler, kapasite = s
    elle = optimizasyon.girilen_sira_rotalari(talepler, kapasite)
    optimize = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite, len(talepler) - 1, sure_limiti_sn=SURE)
    # Çözücü metreye yuvarlanmış mesafelerle çalışır; küçük bir pay bırakıyoruz.
    assert optimizasyon.toplam_uzunluk(matris, optimize) <= optimizasyon.toplam_uzunluk(matris, elle) + 0.01


@AYAR
@given(senaryo())
def test_araci_azalt_elle_plandan_fazla_arac_kullanmaz(s):
    matris, talepler, kapasite = s
    elle = optimizasyon.girilen_sira_rotalari(talepler, kapasite)
    az_arac = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite, len(talepler) - 1, sure_limiti_sn=SURE,
                                              araci_azalt=True)
    assert len(az_arac) <= len(elle)
    assert len(az_arac) >= optimizasyon.gereken_en_az_arac(talepler, kapasite)


@AYAR
@given(st.lists(samsun_noktasi, min_size=3, max_size=7))
def test_tek_arac_kaba_kuvvetle_ayni_optimumu_bulur(noktalar):
    matris = mesafe.tahmini_matris(noktalar)["mesafe_km"]
    en_iyi = min(optimizasyon.rota_uzunlugu(matris, [0, *sira, 0])
                 for sira in itertools.permutations(range(1, len(noktalar))))
    bulunan = optimizasyon.rota_uzunlugu(matris, optimizasyon.en_kisa_rota(matris, sure_limiti_sn=SURE))
    assert bulunan == pytest.approx(en_iyi, abs=0.01)


@AYAR
@given(senaryo(), st.lists(st.integers(400, 1500), min_size=1, max_size=3), st.booleans())
def test_karisik_filoda_her_arac_kendi_kapasitesine_uyar(s, filo, araci_azalt):
    matris, talepler, _ = s
    # Her durağa yetecek kadar araç olsun diye filo tekrarlanır (plan her zaman mümkün)
    kapasiteler = (filo * len(talepler))[: len(talepler) - 1]
    sonuc = optimizasyon.filo_rotalari(matris, talepler, kapasiteler, sure_limiti_sn=SURE, araci_azalt=araci_azalt)
    assert sonuc is not None
    duraklar = sorted(d for _, r in sonuc for d in r[1:-1])
    assert duraklar == list(range(1, len(talepler)))
    for arac, rota in sonuc:
        assert sum(talepler[d] for d in rota) <= kapasiteler[arac]
    # Elle plan da her seferde aracın kapasitesine uymalı
    for arac, rota in optimizasyon.girilen_sira_filo(talepler, kapasiteler):
        assert sum(talepler[d] for d in rota) <= kapasiteler[arac]


# --- Koordinat okuma ------------------------------------------------------------

turkiye_noktasi = st.tuples(st.floats(36.0, 42.0), st.floats(26.0, 44.5))


def _dms(deger, pozitif, negatif):
    yon = pozitif if deger >= 0 else negatif
    deger = abs(deger)
    derece, kalan = int(deger), (abs(deger) - int(deger)) * 60
    dakika = int(kalan)
    return f"{derece}°{dakika}'{(kalan - dakika) * 60:.1f}\"{yon}"


@settings(max_examples=200)
@given(turkiye_noktasi, st.sampled_from(["nokta", "virgul", "parantez", "isimli", "dms"]))
def test_her_bicimde_yazilan_koordinat_dogru_okunur(nokta, bicim):
    enlem, boylam = nokta
    metin = {
        "nokta": f"{enlem:.6f}, {boylam:.6f}",
        "virgul": f"{enlem:.6f}, {boylam:.6f}".replace(".", ","),
        "parantez": f"({enlem:.6f}, {boylam:.6f})",
        "isimli": f"Depo ({enlem:.6f}, {boylam:.6f})",
        "dms": f"{_dms(enlem, 'N', 'S')} {_dms(boylam, 'E', 'W')}",
    }[bicim]
    okunan = geocoding.koordinat_metni_coz(metin)
    assert okunan is not None, metin
    assert okunan[0] == pytest.approx(enlem, abs=1e-4) and okunan[1] == pytest.approx(boylam, abs=1e-4)


# --- Şüpheli konum kontrolü -----------------------------------------------------

@AYAR
@given(st.lists(samsun_noktasi, min_size=4, max_size=10), st.data())
def test_sehir_ici_noktalarda_uyari_yok_ters_yazilan_yakalanir(noktalar, data):
    assert mesafe.supheli_uzak_noktalar(noktalar) == []
    i = data.draw(st.integers(0, len(noktalar) - 1))
    bozuk = list(noktalar)
    bozuk[i] = (noktalar[i][1], noktalar[i][0])  # enlem ile boylam yer değiştirdi
    supheliler = mesafe.supheli_uzak_noktalar(bozuk)
    assert [s["index"] for s in supheliler] == [i]
    assert supheliler[0]["ters_olabilir"]
