"""Sonuç haritasını (folium) çizen modül.

Depo kırmızı "D" ile, her aracın durakları kendi renginde ve ziyaret sırasına göre numaralı gösterilir.
"""

import html

import folium

DEPO_RENGI = "#d1242f"
ARAC_RENKLERI = ["#1f6feb", "#2da44e", "#bf8700", "#8250df", "#0a7f8c"]  # depo kırmızısından farklı


def _daire_ikon(etiket, renk):
    return folium.DivIcon(
        icon_size=(30, 30), icon_anchor=(15, 15),
        html=f'<div style="background:{renk};color:#fff;border:2px solid #fff;border-radius:50%;'
             f'width:30px;height:30px;display:flex;align-items:center;justify-content:center;'
             f'font-weight:700;font-size:13px;box-shadow:0 1px 4px rgba(0,0,0,.4)">{etiket}</div>',
    )


def harita_olustur(sonuc):
    noktalar = sonuc["noktalar"]
    depo = noktalar[0]
    harita = folium.Map(location=[depo["enlem"], depo["boylam"]], zoom_start=12)

    # Her araç kendi renginde: rota çizgisi + ziyaret sırasına göre numaralı duraklar.
    for arac_no, (rota, cizgi) in enumerate(zip(sonuc["optimize_rotalar"], sonuc["cizgiler"], strict=True), start=1):
        renk = ARAC_RENKLERI[(arac_no - 1) % len(ARAC_RENKLERI)]
        folium.PolyLine(cizgi, color=renk, weight=5, opacity=0.8, tooltip=f"Araç {arac_no}").add_to(harita)
        for sira, dugum in enumerate(rota[1:-1], start=1):
            nokta = noktalar[dugum]
            baslik = f"Araç {arac_no} · {sira}. durak"
            # Kullanıcı ve servis metinleri haritaya HTML olarak girer: kaçış yapılmazsa kod çalıştırılabilir.
            adres, bulunan = html.escape(nokta["adres"]), html.escape(nokta["bulunan_adres"])
            folium.Marker(
                [nokta["enlem"], nokta["boylam"]], icon=_daire_ikon(sira, renk),
                tooltip=f"{baslik}: {adres} ({nokta['talep']} kg)",
                popup=folium.Popup(f"<b>{baslik}</b><br>{bulunan}<br>Teslim: {nokta['talep']} kg",
                                   max_width=300),
            ).add_to(harita)

    folium.Marker(
        [depo["enlem"], depo["boylam"]], icon=_daire_ikon("D", DEPO_RENGI),
        tooltip=f"DEPO: {html.escape(depo['adres'])}",
        popup=folium.Popup(f"<b>DEPO</b><br>{html.escape(depo['bulunan_adres'])}", max_width=300),
    ).add_to(harita)

    harita.fit_bounds([[n["enlem"], n["boylam"]] for n in noktalar], padding=(30, 30))
    return harita
