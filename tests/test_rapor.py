import io

import pandas as pd

import rapor

NOKTALAR = [
    {"adres": "Depo", "enlem": 41.0, "boylam": 36.0, "talep": 0},
    {"adres": "A", "enlem": 41.1, "boylam": 36.1, "talep": 100},
    {"adres": "B", "enlem": 41.2, "boylam": 36.2, "talep": 300},
]
MESAFE = [[0, 2, 5], [2, 0, 3], [5, 3, 0]]
SURE = [[0, 4, 10], [4, 0, 6], [10, 6, 0]]


def test_durak_tablosu_kumulatif_degerler_ve_kalan_yuk():
    df = rapor.durak_tablosu([[0, 1, 2, 0]], NOKTALAR, MESAFE, SURE, servis_suresi_dk=5)
    assert list(df["Sıra"]) == ["1", "2", "Dönüş"]
    assert list(df["Kümülatif km"]) == [2, 5, 10]
    assert list(df["Araçta kalan (kg)"]) == [300, 0, 0]
    # sürüş 4+6+10 = 20 dk + 2 durak × 5 dk servis = 30 dk (depoda servis yok)
    assert df["Kümülatif süre (dk)"].iloc[-1] == 30


def test_arac_ozeti_doluluk_orani():
    df = rapor.arac_ozeti([[0, 1, 0], [0, 2, 0]], NOKTALAR, MESAFE, SURE, kapasite=400, servis_suresi_dk=5)
    assert list(df["Yük (kg)"]) == [100, 300]
    assert list(df["Doluluk (%)"]) == [25.0, 75.0]
    assert list(df["Mesafe (km)"]) == [4, 10]
    assert list(df["Süre (dk)"]) == [13, 25]


def test_excel_tum_sayfalari_icerir():
    durak = rapor.durak_tablosu([[0, 1, 2, 0]], NOKTALAR, MESAFE, SURE)
    arac = rapor.arac_ozeti([[0, 1, 2, 0]], NOKTALAR, MESAFE, SURE, kapasite=500)
    veri = rapor.excel_olustur({"Toplam mesafe (km)": 10}, {"Araçlar": arac, "Durak Sırası": durak})
    sayfalar = pd.read_excel(io.BytesIO(veri), sheet_name=None)
    assert set(sayfalar) == {"Özet", "Araçlar", "Durak Sırası"}
    assert len(sayfalar["Durak Sırası"]) == 3
