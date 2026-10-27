"""Sonuç tablosunu hazırlayan ve Excel dosyası üreten yardımcı modül."""

import io

import pandas as pd


def durak_tablosu(rota, noktalar, mesafe_km, sure_dk, servis_suresi_dk=0):
    """Rota sırasına göre durak tablosu (pandas DataFrame) üretir.

    rota: [0, 3, 1, ..., 0] düğüm sırası
    noktalar: geocoding.toplu_koordinat çıktısı (0. eleman depo)
    """
    satirlar = []
    toplam_km = toplam_dk = 0.0
    for sira, (onceki, simdiki) in enumerate(zip(rota, rota[1:]), start=1):
        km = mesafe_km[onceki][simdiki]
        dk = sure_dk[onceki][simdiki]
        depo_mu = simdiki == rota[0]
        toplam_km += km
        toplam_dk += dk + (0 if depo_mu else servis_suresi_dk)
        satirlar.append({
            "Sıra": "Dönüş" if depo_mu else str(sira),
            "Adres": noktalar[simdiki]["adres"] + (" (DEPO)" if depo_mu else ""),
            "Önceki noktadan km": round(km, 2),
            "Önceki noktadan dk": round(dk, 1),
            "Kümülatif km": round(toplam_km, 2),
            "Kümülatif süre (dk)": round(toplam_dk, 1),
            "Enlem": round(noktalar[simdiki]["enlem"], 6),
            "Boylam": round(noktalar[simdiki]["boylam"], 6),
        })
    return pd.DataFrame(satirlar)


def excel_olustur(durak_df, ozet):
    """İki sayfalı Excel dosyasını bellekte oluşturup bytes olarak döner.

    ozet: {"Toplam mesafe (km)": 42.1, ...} gibi bir sözlük.
    """
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as yazici:
        pd.DataFrame(list(ozet.items()), columns=["Metrik", "Değer"]).to_excel(yazici, sheet_name="Özet", index=False)
        durak_df.to_excel(yazici, sheet_name="Durak Sırası", index=False)
        for sayfa in yazici.sheets.values():
            for sutun in sayfa.columns:
                genislik = max(len(str(h.value or "")) for h in sutun)
                sayfa.column_dimensions[sutun[0].column_letter].width = min(genislik + 2, 70)
    return tampon.getvalue()
