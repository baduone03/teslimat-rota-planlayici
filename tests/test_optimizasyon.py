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
