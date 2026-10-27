"""Sonuç tablolarını hazırlayan ve Excel dosyası üreten yardımcı modül.

noktalar: her eleman {"adres", "enlem", "boylam", "talep", ...} sözlüğü; 0. eleman depo.
rotalar:  her araç için [0, 3, 1, ..., 0] düğüm sırası.
"""

import io

import pandas as pd


def rota_suresi(rota, sure_dk, servis_suresi_dk=0):
    """Sürüş süresi + (durak sayısı × durak başı teslim süresi)."""
    surus = sum(sure_dk[a][b] for a, b in zip(rota, rota[1:], strict=False))
    return surus + servis_suresi_dk * (len(rota) - 2)


def _adlar(rotalar, arac_adlari):
    return arac_adlari or [str(i) for i in range(1, len(rotalar) + 1)]


def durak_tablosu(rotalar, noktalar, mesafe_km, sure_dk, servis_suresi_dk=0, arac_adlari=None):
    """Araç ve ziyaret sırasına göre durak tablosu (pandas DataFrame).
    arac_adlari: her rota için araç adı (ör. "Kamyon", "Kamyonet 1"); verilmezse 1, 2, 3..."""
    satirlar = []
    for arac_no, rota in zip(_adlar(rotalar, arac_adlari), rotalar, strict=True):
        kalan_yuk = sum(noktalar[d].get("talep", 0) for d in rota[1:-1])
        toplam_km = toplam_dk = 0.0
        for sira, (onceki, simdiki) in enumerate(zip(rota, rota[1:], strict=False), start=1):
            km = mesafe_km[onceki][simdiki]
            dk = sure_dk[onceki][simdiki]
            depo_mu = simdiki == rota[0]
            teslim = 0 if depo_mu else noktalar[simdiki].get("talep", 0)
            kalan_yuk -= teslim
            toplam_km += km
            toplam_dk += dk + (0 if depo_mu else servis_suresi_dk)
            satirlar.append({
                "Araç": arac_no,
                "Sıra": "Dönüş" if depo_mu else str(sira),
                "Adres": noktalar[simdiki]["adres"] + (" (DEPO)" if depo_mu else ""),
                "Teslim (kg)": teslim,
                "Araçta kalan (kg)": kalan_yuk,
                "Önceki noktadan km": round(km, 2),
                "Önceki noktadan dk": round(dk, 1),
                "Kümülatif km": round(toplam_km, 2),
                "Kümülatif süre (dk)": round(toplam_dk, 1),
                "Enlem": round(noktalar[simdiki]["enlem"], 6),
                "Boylam": round(noktalar[simdiki]["boylam"], 6),
            })
    return pd.DataFrame(satirlar)


def arac_ozeti(rotalar, noktalar, mesafe_km, sure_dk, kapasite=None, servis_suresi_dk=0, arac_adlari=None):
    """Her araç için durak sayısı, yük, kapasite, doluluk oranı, km ve süre.
    kapasite: tüm araçlar için tek sayı ya da her rota için ayrı liste (karışık filo)."""
    kapasiteler = kapasite if isinstance(kapasite, (list, tuple)) else [kapasite] * len(rotalar)
    satirlar = []
    for arac_no, rota, kap in zip(_adlar(rotalar, arac_adlari), rotalar, kapasiteler, strict=True):
        yuk = sum(noktalar[d].get("talep", 0) for d in rota[1:-1])
        satirlar.append({
            "Araç": arac_no,
            "Durak sayısı": len(rota) - 2,
            "Yük (kg)": yuk,
            "Kapasite (kg)": kap,
            "Doluluk (%)": round(yuk / kap * 100, 1) if kap else None,
            "Mesafe (km)": round(sum(mesafe_km[a][b] for a, b in zip(rota, rota[1:], strict=False)), 2),
            "Süre (dk)": round(rota_suresi(rota, sure_dk, servis_suresi_dk), 1),
        })
    return pd.DataFrame(satirlar)


def excel_olustur(ozet, sayfalar):
    """Özet + verilen tablolardan çok sayfalı Excel dosyasını bellekte oluşturur.

    ozet: {"Toplam mesafe (km)": 42.1, ...} gibi bir sözlük.
    sayfalar: {"Sayfa adı": DataFrame, ...}
    """
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as yazici:
        pd.DataFrame(list(ozet.items()), columns=["Metrik", "Değer"]).to_excel(yazici, sheet_name="Özet", index=False)
        for ad, df in sayfalar.items():
            df.to_excel(yazici, sheet_name=ad, index=False)
        for sayfa in yazici.sheets.values():
            for sutun in sayfa.columns:
                genislik = max(len(str(h.value or "")) for h in sutun)
                sayfa.column_dimensions[sutun[0].column_letter].width = min(genislik + 2, 70)
    return tampon.getvalue()
