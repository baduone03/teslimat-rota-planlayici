import io

import pandas as pd

import rapor

NOKTALAR = [
    {"adres": "Depo", "enlem": 41.0, "boylam": 36.0},
    {"adres": "A", "enlem": 41.1, "boylam": 36.1},
    {"adres": "B", "enlem": 41.2, "boylam": 36.2},
]
MESAFE = [[0, 2, 5], [2, 0, 3], [5, 3, 0]]
SURE = [[0, 4, 10], [4, 0, 6], [10, 6, 0]]


def test_durak_tablosu_kumulatif_degerler():
    df = rapor.durak_tablosu([0, 1, 2, 0], NOKTALAR, MESAFE, SURE, servis_suresi_dk=5)
    assert list(df["Sıra"]) == ["1", "2", "Dönüş"]
    assert list(df["Kümülatif km"]) == [2, 5, 10]
    # sürüş 4+6+10 = 20 dk + 2 durak × 5 dk servis = 30 dk (depoda servis yok)
    assert df["Kümülatif süre (dk)"].iloc[-1] == 30


def test_excel_iki_sayfa_icerir():
    df = rapor.durak_tablosu([0, 1, 2, 0], NOKTALAR, MESAFE, SURE)
    veri = rapor.excel_olustur(df, {"Toplam mesafe (km)": 10})
    sayfalar = pd.read_excel(io.BytesIO(veri), sheet_name=None)
    assert set(sayfalar) == {"Özet", "Durak Sırası"}
    assert len(sayfalar["Durak Sırası"]) == 3
