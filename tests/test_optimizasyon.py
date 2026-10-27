import itertools

import pytest

import optimizasyon
from mesafe import tahmini_matris


def _kaba_kuvvet_en_kisa(matris):
    """Küçük örneklerde tüm sıraları deneyip gerçek en kısayı bulur (kontrol için)."""
    n = len(matris)
    return min(
        optimizasyon.rota_uzunlugu(matris, [0, *sira, 0])
        for sira in itertools.permutations(range(1, n))
    )


def test_duz_cizgideki_noktalar_sirayla_ziyaret_edilir():
    # Bir doğru üzerinde 0, 1, 2, 3, 4 km'deki noktalar; karışık sırada verildi.
    konumlar = [0, 3, 1, 4, 2]
    matris = [[abs(a - b) for b in konumlar] for a in konumlar]
    rota = optimizasyon.en_kisa_rota(matris, sure_limiti_sn=1)

    assert rota[0] == 0 and rota[-1] == 0
    assert sorted(rota[1:-1]) == [1, 2, 3, 4]  # her durak tam bir kez
    assert optimizasyon.rota_uzunlugu(matris, rota) == 8  # 0→4 gidiş + dönüş


def test_samsun_benzeri_ornekte_optimum_bulunur():
    noktalar = [(41.21, 36.46), (41.36, 36.22), (41.27, 36.36), (41.29, 36.33),
                (41.32, 36.29), (41.26, 36.37), (41.28, 36.32)]
    matris = tahmini_matris(noktalar)["mesafe_km"]
    rota = optimizasyon.en_kisa_rota(matris, sure_limiti_sn=1)
    assert optimizasyon.rota_uzunlugu(matris, rota) == pytest.approx(_kaba_kuvvet_en_kisa(matris), abs=0.01)


def test_optimize_rota_girilen_siradan_uzun_olamaz():
    noktalar = [(41.21, 36.46), (41.36, 36.22), (41.26, 36.37), (41.33, 36.27), (41.27, 36.36)]
    matris = tahmini_matris(noktalar)["mesafe_km"]
    girilen = optimizasyon.rota_uzunlugu(matris, optimizasyon.girilen_sira_rotasi(len(noktalar)))
    optimize = optimizasyon.rota_uzunlugu(matris, optimizasyon.en_kisa_rota(matris, sure_limiti_sn=1))
    assert optimize <= girilen + 1e-9


def test_girilen_sira_ve_tasarruf():
    assert optimizasyon.girilen_sira_rotasi(4) == [0, 1, 2, 3, 0]
    assert optimizasyon.tasarruf_yuzdesi(100, 75) == 25
    assert optimizasyon.tasarruf_yuzdesi(0, 0) == 0


# --- Araç kapasitesi (CVRP) ---------------------------------------------------

def _her_durak_bir_kez(rotalar, n):
    duraklar = [d for rota in rotalar for d in rota[1:-1]]
    return sorted(duraklar) == list(range(1, n))


def test_kapasite_asilmaz_ve_her_durak_bir_kez_ziyaret_edilir():
    noktalar = [(41.21, 36.46), (41.36, 36.22), (41.27, 36.36), (41.29, 36.33),
                (41.32, 36.29), (41.26, 36.37), (41.28, 36.32), (41.33, 36.27)]
    matris = tahmini_matris(noktalar)["mesafe_km"]
    talepler = [0, 300, 250, 200, 350, 150, 100, 250]  # toplam 1600 kg
    rotalar = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite=700, arac_sayisi=3, sure_limiti_sn=1)

    assert rotalar is not None and len(rotalar) == 3  # 1600/700 → en az 3 araç
    assert _her_durak_bir_kez(rotalar, len(noktalar))
    for rota in rotalar:
        assert rota[0] == 0 and rota[-1] == 0
        assert sum(talepler[d] for d in rota) <= 700


def test_depo_ortadaysa_her_arac_bir_tarafa_gider():
    # Doğru üzerinde: depo 0 km'de; 1,2 solda (-1, -2 km), 3,4 sağda (+1, +2 km).
    konumlar = [0, -1, -2, 1, 2]
    matris = [[abs(a - b) for b in konumlar] for a in konumlar]
    talepler = [0, 5, 5, 5, 5]
    rotalar = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite=10, arac_sayisi=2, sure_limiti_sn=1)

    taraflar = sorted(sorted(rota[1:-1]) for rota in rotalar)
    assert taraflar == [[1, 2], [3, 4]]
    assert optimizasyon.toplam_uzunluk(matris, rotalar) == 8


def test_kapasite_yetmezse_none_doner():
    matris = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    assert optimizasyon.kapasiteli_rotalar(matris, [0, 8, 8], kapasite=10, arac_sayisi=1, sure_limiti_sn=1) is None


def test_girilen_sira_araclari_sirayla_doldurur():
    assert optimizasyon.girilen_sira_rotalari([0, 5, 5, 5], kapasite=10) == [[0, 1, 2, 0], [0, 3, 0]]
    assert optimizasyon.girilen_sira_rotalari([0, 5, 5, 5]) == [[0, 1, 2, 3, 0]]
    assert optimizasyon.gereken_en_az_arac([0, 5, 5, 5], 10) == 2


def test_araci_azalt_secenegi_arac_sayisini_dusurur():
    # Doğru üzerinde: doğuda 2 durak (+10 km), batıda 2 durak (-10 km), depoya yakın 1 durak (+1 km).
    # Talepler kapasiteyi zorluyor: sadece km'ye bakılırsa 3 araç (doğu, batı, yakın) en kısası;
    # 2 araçla da taşınabilir ama araçlar doğu-batı arasında gidip gelmek zorunda kalır.
    konumlar = [0, 10, 10, -10, -10, 1]
    matris = [[abs(a - b) for b in konumlar] for a in konumlar]
    talepler = [0, 5, 3, 5, 3, 4]  # toplam 20 kg, kapasite 10 → en az 2 araç

    sadece_km = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite=10, arac_sayisi=3, sure_limiti_sn=1)
    az_arac = optimizasyon.kapasiteli_rotalar(matris, talepler, kapasite=10, arac_sayisi=3, sure_limiti_sn=1,
                                              araci_azalt=True)

    assert len(sadece_km) == 3 and optimizasyon.toplam_uzunluk(matris, sadece_km) == 42
    assert len(az_arac) == 2
    assert _her_durak_bir_kez(az_arac, len(konumlar))
    assert all(sum(talepler[d] for d in r) <= 10 for r in az_arac)


# --- Farklı kapasiteli araçlar (karışık filo) -------------------------------------

def test_her_arac_kendi_kapasitesini_asmaz_agir_yuk_kamyona_gider():
    noktalar = [(41.28, 36.35), (41.36, 36.23), (41.23, 36.45), (41.30, 36.33), (41.27, 36.34), (41.33, 36.28)]
    matris = tahmini_matris(noktalar)["mesafe_km"]
    talepler = [0, 900, 200, 150, 250, 100]        # 900 kg'lık yük yalnızca kamyona sığar
    kapasiteler = [1000, 600, 600]                  # 0: kamyon, 1-2: kamyonet
    sonuc = optimizasyon.filo_rotalari(matris, talepler, kapasiteler, sure_limiti_sn=1)

    assert _her_durak_bir_kez([r for _, r in sonuc], len(noktalar))
    for arac, rota in sonuc:
        assert sum(talepler[d] for d in rota) <= kapasiteler[arac]
    kamyon_rotasi = next(r for a, r in sonuc if a == 0)
    assert 1 in kamyon_rotasi


def test_elle_plan_filoyu_sirayla_kullanir_ve_basa_doner():
    # Kamyon 10, kamyonet 5: 4+4 kamyona; sonraki 4 sığmaz → kamyonet; sonraki 4 kamyonete sığmaz → kamyon (2. sefer)
    beklenen = [(0, [0, 1, 2, 0]), (1, [0, 3, 0]), (0, [0, 4, 0])]
    assert optimizasyon.girilen_sira_filo([0, 4, 4, 4, 4], [10, 5]) == beklenen


def test_elle_plan_yuku_tasiyamayan_araci_atlar():
    assert optimizasyon.girilen_sira_filo([0, 8], [5, 10]) == [(1, [0, 1, 0])]


def test_filo_hatalari():
    assert optimizasyon.filo_hatalari([300, 200], [1000, 600]) == []
    hatalar = optimizasyon.filo_hatalari([1200, 500], [1000, 600], adlar=["Büyük", "Küçük"])  # toplam 1700 > 1600
    assert "en büyük aracın kapasitesinden (1000 kg) fazla: Büyük" in hatalar[0]
    assert "toplam kapasitesi 1600 kg" in hatalar[1]
    assert optimizasyon.filo_hatalari([100], []) == ["Filoda en az bir araç olmalı."]


def test_filoyu_ac_araclari_numaralandirir():
    adlar, kapasiteler = optimizasyon.filoyu_ac([("Kamyon", 1000, 1), ("Kamyonet", 600, 2)])
    assert adlar == ["Kamyon", "Kamyonet 1", "Kamyonet 2"]
    assert kapasiteler == [1000, 600, 600]
    # Aynı tip iki ayrı satırda da olsa numara kesintisiz devam eder
    assert optimizasyon.filoyu_ac([("Van", 500, 1), ("Van", 700, 1)])[0] == ["Van 1", "Van 2"]


def test_esdeger_araclar_sirayla_numaralanir():
    turler = [("Kamyon", 1000), ("Kamyonet", 600), ("Kamyonet", 600)]
    plan = [(0, [0, 1, 0]), (2, [0, 2, 0])]           # çözücü "Kamyonet 2"yi seçmiş
    assert optimizasyon.esdeger_araclari_sirala(plan, turler) == [(0, [0, 1, 0]), (1, [0, 2, 0])]
    # Farklı kapasiteli aynı isimli araçlar birbirine karıştırılmaz
    assert optimizasyon.esdeger_araclari_sirala([(1, [0, 1, 0])], [("Van", 500), ("Van", 700)]) == [(1, [0, 1, 0])]
