"""Teslimat Rota Planlayıcı — Streamlit arayüzü.

Akış: Adresler → (geocoding) koordinatlar → (mesafe) mesafe matrisi
      → (optimizasyon) en kısa sıra → harita + tablo + karşılaştırma + Excel
Çalıştırma: streamlit run app.py
"""

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import geocoding
import mesafe
import optimizasyon
import rapor
from ornek_veriler import ORNEK_ADRESLER, ORNEK_DEPO, YEDEK_KOORDINATLAR

MIN_ADRES, MAX_ADRES = 3, 15

st.set_page_config(page_title="Teslimat Rota Planlayıcı", page_icon="🚚", layout="wide")


# ---------------------------------------------------------------------------
# Hesaplama
# ---------------------------------------------------------------------------
def rotayi_hesapla(depo, adresler, servis_suresi_dk):
    """Tüm adımları sırayla çalıştırıp sonuçları bir sözlükte döner."""
    tum_adresler = [depo] + adresler  # 0. indeks her zaman depo

    # 1) Adres → koordinat
    cubuk = st.progress(0.0, text="Adresler koordinata çevriliyor…")
    noktalar = geocoding.toplu_koordinat(
        tum_adresler,
        yedek_koordinatlar=YEDEK_KOORDINATLAR,
        ilerleme=lambda i, n, adres: cubuk.progress(i / n, text=f"Konum aranıyor ({i}/{n}): {adres}"),
    )
    cubuk.empty()

    if noktalar[0]["kaynak"] == "bulunamadi":
        st.error(f"Depo adresi bulunamadı: **{depo}**. Lütfen daha açık yazın (ör. 'Mahalle, İlçe, İl').")
        return None
    bulunamayanlar = [n["adres"] for n in noktalar if n["kaynak"] == "bulunamadi"]
    noktalar = [n for n in noktalar if n["kaynak"] != "bulunamadi"]
    if len(noktalar) - 1 < MIN_ADRES:
        st.error(f"En az {MIN_ADRES} teslimat adresi bulunmalı. Bulunamayanlar: {', '.join(bulunamayanlar)}")
        return None

    koordinatlar = [(n["enlem"], n["boylam"]) for n in noktalar]

    # 2) Mesafe ve süre matrisi
    with st.spinner("Yol mesafeleri hesaplanıyor (OSRM)…"):
        matris = mesafe.mesafe_matrisi(koordinatlar)

    # 3) Optimizasyon + girilen sıra ile karşılaştırma
    with st.spinner("En kısa rota aranıyor (OR-Tools)…"):
        optimize_rota = optimizasyon.en_kisa_rota(matris["mesafe_km"])
    girilen_rota = optimizasyon.girilen_sira_rotasi(len(noktalar))

    # 4) Harita için gerçek yol çizgisi
    with st.spinner("Rota çizgisi hazırlanıyor…"):
        cizgi = mesafe.rota_geometrisi([koordinatlar[i] for i in optimize_rota])

    def ozet(rota):
        km = optimizasyon.rota_uzunlugu(matris["mesafe_km"], rota)
        dk = optimizasyon.rota_uzunlugu(matris["sure_dk"], rota) + servis_suresi_dk * (len(noktalar) - 1)
        return km, dk

    return {
        "noktalar": noktalar,
        "matris": matris,
        "optimize_rota": optimize_rota,
        "optimize": ozet(optimize_rota),
        "girilen": ozet(girilen_rota),
        "cizgi": cizgi,
        "bulunamayanlar": bulunamayanlar,
        "servis_suresi_dk": servis_suresi_dk,
    }


def sure_metni(dakika):
    saat, dk = divmod(round(dakika), 60)
    return f"{saat} sa {dk} dk" if saat else f"{dk} dk"


def harita_olustur(sonuc):
    noktalar, rota = sonuc["noktalar"], sonuc["optimize_rota"]
    harita = folium.Map(location=[noktalar[0]["enlem"], noktalar[0]["boylam"]], zoom_start=12)

    folium.PolyLine(sonuc["cizgi"], color="#1f6feb", weight=5, opacity=0.8, tooltip="Optimize rota").add_to(harita)

    # Depo: kırmızı "D"; teslimat durakları: ziyaret sırasına göre numaralı mavi daire.
    for sira, dugum in enumerate(rota[:-1]):
        nokta = noktalar[dugum]
        depo_mu = sira == 0
        etiket, renk = ("D", "#d1242f") if depo_mu else (str(sira), "#1f6feb")
        ikon = folium.DivIcon(
            icon_size=(30, 30), icon_anchor=(15, 15),
            html=f'<div style="background:{renk};color:#fff;border:2px solid #fff;border-radius:50%;'
                 f'width:30px;height:30px;display:flex;align-items:center;justify-content:center;'
                 f'font-weight:700;font-size:13px;box-shadow:0 1px 4px rgba(0,0,0,.4)">{etiket}</div>',
        )
        baslik = "DEPO" if depo_mu else f"{sira}. durak"
        folium.Marker(
            [nokta["enlem"], nokta["boylam"]], icon=ikon,
            tooltip=f"{baslik}: {nokta['adres']}",
            popup=folium.Popup(f"<b>{baslik}</b><br>{nokta['bulunan_adres']}", max_width=300),
        ).add_to(harita)

    harita.fit_bounds([[n["enlem"], n["boylam"]] for n in noktalar], padding=(30, 30))
    return harita


# ---------------------------------------------------------------------------
# Arayüz
# ---------------------------------------------------------------------------
st.title("🚚 Teslimat Rota Planlayıcı")
st.caption("Depodan çıkıp tüm adreslere uğrayan ve depoya dönen **en kısa** rotayı hesaplar. "
           "Ücretsiz servisler: OpenStreetMap Nominatim, OSRM, Google OR-Tools.")

with st.sidebar:
    st.header("📍 Girdiler")
    depo = st.text_input("Depo (başlangıç ve bitiş noktası)", value=ORNEK_DEPO)
    st.markdown(f"**Teslimat adresleri** ({MIN_ADRES}–{MAX_ADRES} adet)")
    adres_tablosu = st.data_editor(
        pd.DataFrame({"Adres": ORNEK_ADRESLER}),
        num_rows="dynamic", hide_index=True, key="adresler", width="stretch",
    )
    servis_suresi = st.number_input("Durak başı teslim süresi (dk)", min_value=0, max_value=60, value=5)
    hesapla = st.button("Rotayı Hesapla", type="primary", width="stretch")
    st.caption("İpucu: Adresleri 'Mahalle, İlçe, İl' biçiminde yazın. "
               "Nominatim kuralı gereği her adres ~1 sn sürer; aynı adres ikinci kez hızlı gelir.")

if hesapla:
    adresler = [str(a).strip() for a in adres_tablosu["Adres"].dropna() if str(a).strip()]
    if not depo.strip():
        st.error("Depo adresi boş olamaz.")
    elif not MIN_ADRES <= len(adresler) <= MAX_ADRES:
        st.error(f"{MIN_ADRES} ile {MAX_ADRES} arasında teslimat adresi girin (şu an {len(adresler)}).")
    else:
        # Sonucu session_state'e koyuyoruz: harita etkileşiminde sayfa yenilense de kaybolmasın.
        st.session_state["sonuc"] = rotayi_hesapla(depo.strip(), adresler, servis_suresi)

sonuc = st.session_state.get("sonuc")
if not sonuc:
    st.info("👈 Soldan depo ve adresleri girip **Rotayı Hesapla**'ya basın. Samsun örnek adresleri hazır.")
    st.stop()

# --- Uyarılar
if sonuc["bulunamayanlar"]:
    st.warning("Bulunamadığı için rotaya eklenmeyen adresler: " + ", ".join(sonuc["bulunamayanlar"]))
if any(n["kaynak"] == "yedek" for n in sonuc["noktalar"]):
    st.warning("Konum servisine ulaşılamadı; bazı örnek adresler için kayıtlı **yaklaşık** koordinatlar kullanıldı.")
if sonuc["matris"]["kaynak"] == "tahmini":
    st.warning("Yol mesafesi servisine (OSRM) ulaşılamadı; mesafeler kuş uçuşu × "
               f"{mesafe.YOL_KATSAYISI} ile **tahmini** hesaplandı.")

# --- Özet kartları
opt_km, opt_dk = sonuc["optimize"]
gir_km, gir_dk = sonuc["girilen"]
k1, k2, k3 = st.columns(3)
k1.metric("Toplam mesafe", f"{opt_km:.1f} km")
k2.metric("Tahmini süre", sure_metni(opt_dk), help="Sürüş süresi + durak başı teslim süresi")
k3.metric("Teslimat durağı", len(sonuc["noktalar"]) - 1)

# --- Karşılaştırma kutusu
tasarruf = optimizasyon.tasarruf_yuzdesi(gir_km, opt_km)
st.success(
    f"📊 **Girilen sırayla gitseydin {gir_km:.1f} km**, **optimize rota {opt_km:.1f} km** → "
    f"**tasarruf %{tasarruf:.1f}** ({gir_km - opt_km:.1f} km, yaklaşık {sure_metni(max(gir_dk - opt_dk, 0))} daha az)."
)

# --- Harita ve tablo
sol, sag = st.columns([3, 2])
with sol:
    st.subheader("🗺️ Rota haritası")
    st_folium(harita_olustur(sonuc), height=520, use_container_width=True, returned_objects=[])
with sag:
    st.subheader("📋 Durak sırası")
    tablo = rapor.durak_tablosu(
        sonuc["optimize_rota"], sonuc["noktalar"],
        sonuc["matris"]["mesafe_km"], sonuc["matris"]["sure_dk"], sonuc["servis_suresi_dk"],
    )
    st.dataframe(tablo.drop(columns=["Enlem", "Boylam"]), hide_index=True, width="stretch")

# --- Excel indirme
ozet = {
    "Depo": sonuc["noktalar"][0]["adres"],
    "Teslimat durağı sayısı": len(sonuc["noktalar"]) - 1,
    "Optimize rota (km)": round(opt_km, 2),
    "Optimize rota süresi (dk)": round(opt_dk, 1),
    "Girilen sıra (km)": round(gir_km, 2),
    "Girilen sıra süresi (dk)": round(gir_dk, 1),
    "Tasarruf (%)": round(tasarruf, 1),
    "Durak başı teslim süresi (dk)": sonuc["servis_suresi_dk"],
    "Mesafe kaynağı": "OSRM (gerçek yol)" if sonuc["matris"]["kaynak"] == "osrm" else "Tahmini (kuş uçuşu × katsayı)",
}
st.download_button(
    "⬇️ Sonucu Excel olarak indir",
    data=rapor.excel_olustur(tablo, ozet),
    file_name="teslimat_rotasi.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
