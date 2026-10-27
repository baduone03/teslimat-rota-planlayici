import harita

NOKTALAR = [
    {"adres": "<img src=x onerror=alert(1)>Depo", "bulunan_adres": "<script>alert(2)</script>",
     "enlem": 41.27, "boylam": 36.35, "talep": 0},
    {"adres": "A <b>kalın</b>", "bulunan_adres": "A", "enlem": 41.30, "boylam": 36.30, "talep": 5},
]
SONUC = {"noktalar": NOKTALAR, "optimize_rotalar": [[0, 1, 0]],
         "cizgiler": [[(41.27, 36.35), (41.30, 36.30), (41.27, 36.35)]]}


def test_kullanici_metni_haritada_html_olarak_calismaz():
    kaynak = harita.harita_olustur(SONUC).get_root().render()
    assert "<img src=x onerror=alert(1)>" not in kaynak
    assert "<script>alert(2)</script>" not in kaynak
    assert "<b>kalın</b>" not in kaynak
    assert "&lt;img src=x onerror=alert(1)&gt;" in kaynak  # metin görünür ama zararsız


def test_her_durak_ve_depo_icin_isaret_cizilir():
    kaynak = harita.harita_olustur(SONUC).get_root().render()
    assert kaynak.count("L.marker(") == 2
    assert kaynak.count("L.polyline(") == 1
