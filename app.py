"""Teslimat Rota Planlayıcı — Streamlit arayüzü.

Akış: Adresler → (geocoding) koordinatlar → (mesafe) mesafe matrisi
      → (optimizasyon) araç rotaları → harita + tablolar + karşılaştırma + Excel
Çalıştırma: streamlit run app.py
"""

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import geocoding
import harita
import mesafe
import optimizasyon
import rapor
from ornek_veriler import ORNEK_ADRESLER, ORNEK_ARAC_SAYISI, ORNEK_DEPO, ORNEK_KAPASITE_KG, ORNEK_TALEPLER

MIN_ADRES, MAX_ADRES = 3, 15
MAX_ARAC = 5

st.set_page_config(page_title="Teslimat Rota Planlayıcı", page_icon="🚚", layout="wide")


# ---------------------------------------------------------------------------
# Hesaplama
# ---------------------------------------------------------------------------
def rotayi_hesapla(depo, adresler, talepler, kapasite, arac_sayisi, servis_suresi_dk, araci_azalt):
    """Tüm adımları sırayla çalıştırıp sonuçları bir sözlükte döner."""
    tum_adresler = [depo] + adresler  # 0. indeks her zaman depo

    # 1) Adres → koordinat
    cubuk = st.progress(0.0, text="Adresler koordinata çevriliyor…")
    noktalar = geocoding.toplu_koordinat(
        tum_adresler,
        ilerleme=lambda i, n, adres: cubuk.progress(i / n, text=f"Konum aranıyor ({i}/{n}): {adres}"),
    )
    cubuk.empty()
    # Talebi noktanın içine koyuyoruz: bulunamayan adresler elenince talepler kaymasın.
    for nokta, talep in zip(noktalar, [0] + talepler, strict=True):
        nokta["talep"] = talep

    if noktalar[0]["kaynak"] == "bulunamadi":
        st.error(f"Depo adresi bulunamadı: **{depo}**. Lütfen daha açık yazın (ör. 'Mahalle, İlçe, İl') "
                 "veya koordinat girin (ör. '41.2867, 36.33').")
        return None
    bulunamayanlar = [n["adres"] for n in noktalar if n["kaynak"] == "bulunamadi"]
    noktalar = [n for n in noktalar if n["kaynak"] != "bulunamadi"]
    # "Depo (41.27, 36.35)" gibi koordinatlı girişlerde tablolarda yalnızca isim görünsün.
    for n in noktalar:
        if n["kaynak"] == "koordinat":
            n["adres"] = n["bulunan_adres"]
    if len(noktalar) - 1 < MIN_ADRES:
        st.error(f"En az {MIN_ADRES} teslimat adresi bulunmalı. Bulunamayanlar: {', '.join(bulunamayanlar)}")
        return None

    koordinatlar = [(n["enlem"], n["boylam"]) for n in noktalar]
    talep_listesi = [n["talep"] for n in noktalar]

    # 2) Mesafe ve süre matrisi
    with st.spinner("Yol mesafeleri hesaplanıyor (OSRM)…"):
        matris = mesafe.mesafe_matrisi(koordinatlar)

    # 3) Optimizasyon + girilen sıra ile karşılaştırma
    with st.spinner("En kısa rotalar aranıyor (OR-Tools)…"):
        optimize_rotalar = optimizasyon.kapasiteli_rotalar(
            matris["mesafe_km"], talep_listesi, kapasite, arac_sayisi, sure_limiti_sn=3, araci_azalt=araci_azalt,
        )
    if optimize_rotalar is None:
        st.error(f"{arac_sayisi} araç × {kapasite} kg ile tüm teslimatları taşıyan bir plan bulunamadı. "
                 "Araç sayısını veya kapasiteyi artırın.")
        return None
    girilen_rotalar = optimizasyon.girilen_sira_rotalari(talep_listesi, kapasite)

    # 4) Harita için her aracın gerçek yol çizgisi
    with st.spinner("Rota çizgileri hazırlanıyor…"):
        cizgiler = [mesafe.rota_geometrisi([koordinatlar[i] for i in rota]) for rota in optimize_rotalar]

    def ozet(rotalar):
        km = optimizasyon.toplam_uzunluk(matris["mesafe_km"], rotalar)
        dk = sum(rapor.rota_suresi(r, matris["sure_dk"], servis_suresi_dk) for r in rotalar)
        return km, dk, len(rotalar)

    return {
        "noktalar": noktalar,
        "matris": matris,
        "optimize_rotalar": optimize_rotalar,
        "optimize": ozet(optimize_rotalar),
        "girilen": ozet(girilen_rotalar),
        "cizgiler": cizgiler,
        "bulunamayanlar": bulunamayanlar,
        "supheli_konumlar": supheli_konumlar(noktalar),
        "kapasite": kapasite,
        "araci_azalt": araci_azalt,
        "arac_sayisi": arac_sayisi,
        "servis_suresi_dk": servis_suresi_dk,
    }


def supheli_konumlar(noktalar):
    """Türkiye dışına ya da diğer noktalardan çok uzağa düşen konumlar için uyarı metinleri."""
    uyarilar = {}
    for s in mesafe.supheli_uzak_noktalar([(n["enlem"], n["boylam"]) for n in noktalar]):
        metin = f"diğer noktalara ~{s['km']:.0f} km uzakta"
        if s["ters_olabilir"]:
            metin += " — **enlem ile boylam ters yazılmış olabilir**"
        uyarilar[s["index"]] = metin
    for i, n in enumerate(noktalar):
        if not geocoding.turkiye_icinde(n["enlem"], n["boylam"]):
            uyarilar[i] = "Türkiye sınırları dışında" + (f"; {uyarilar[i]}" if i in uyarilar else "")
    return [f"{'DEPO: ' if i == 0 else ''}{noktalar[i]['adres']} ({noktalar[i]['enlem']:.4f}, "
            f"{noktalar[i]['boylam']:.4f}) → {metin}" for i, metin in sorted(uyarilar.items())]


def sure_metni(dakika):
    saat, dk = divmod(round(dakika), 60)
    return f"{saat} sa {dk} dk" if saat else f"{dk} dk"


# ---------------------------------------------------------------------------
# Arayüz
# ---------------------------------------------------------------------------
st.title("🚚 Teslimat Rota Planlayıcı")
st.caption("Depodan çıkıp tüm adreslere uğrayan ve depoya dönen **en kısa** rotaları, araç kapasitesini "
           "aşmadan hesaplar. Ücretsiz servisler: OpenStreetMap Nominatim, OSRM, Google OR-Tools.")

with st.sidebar:
    st.header("📍 Girdiler")
    depo = st.text_input("Depo (başlangıç ve bitiş noktası)", value=ORNEK_DEPO)
    st.markdown(f"**Teslimat adresleri** ({MIN_ADRES}–{MAX_ADRES} adet)")
    adres_tablosu = st.data_editor(
        pd.DataFrame({"Adres": ORNEK_ADRESLER, "Talep (kg)": ORNEK_TALEPLER}),
        num_rows="dynamic", hide_index=True, key="adresler", width="stretch",
        column_config={
            "Adres": st.column_config.TextColumn(width=140),
            "Talep (kg)": st.column_config.NumberColumn("kg", width=60, min_value=0, step=1, default=0, format="%d"),
        },
    )

    st.markdown("**🚛 Araç filosu**")
    kapasite = st.number_input("Araç kapasitesi (kg)", min_value=1, value=ORNEK_KAPASITE_KG, step=50)
    arac_sayisi = st.number_input("En fazla araç sayısı", min_value=1, max_value=MAX_ARAC, value=ORNEK_ARAC_SAYISI)
    araci_azalt = st.checkbox(
        "Araç sayısını en aza indir", value=True,
        help="Açık: önce mümkün olan en az araç, sonra en kısa km. Kapalı: yalnızca toplam km en aza indirilir; "
             "bu durumda yarı boş bir araç yakındaki tek bir durağa gönderilebilir.",
    )
    servis_suresi = st.number_input("Durak başı teslim süresi (dk)", min_value=0, max_value=60, value=5)
    hesapla = st.button("Rotayı Hesapla", type="primary", width="stretch")
    st.caption("İpucu: Adresleri 'Mahalle, İlçe, İl' biçiminde yazın. Bulunamayan bir yer için adres yerine "
               "'41.2867, 36.33' veya 'Depo (41.2867, 36.33)' gibi enlem, boylam da yazabilirsiniz "
               "(Google Haritalar'da noktaya basılı tutun). Kapasite kısıtı istemiyorsanız talepleri 0 bırakın. "
               "Her adres ~1 sn sürer; aynı adres ikinci kez hızlı gelir.")

satirlar = adres_tablosu.dropna(subset=["Adres"])
satirlar = satirlar[satirlar["Adres"].astype(str).str.strip() != ""]
adresler = satirlar["Adres"].astype(str).str.strip().tolist()
talepler = satirlar["Talep (kg)"].fillna(0).astype(int).tolist()
# Ekrandaki sonucun hangi girdilerle hesaplandığını anlamak için girdilerin "imzası"
girdi_imzasi = (depo.strip(), tuple(adresler), tuple(talepler), int(kapasite), int(arac_sayisi),
                int(servis_suresi), bool(araci_azalt))

if hesapla:
    en_az_arac = optimizasyon.gereken_en_az_arac(talepler, kapasite)
    asiri = [a for a, t in zip(adresler, talepler, strict=True) if t > kapasite]

    if not depo.strip():
        st.error("Depo adresi boş olamaz.")
    elif not MIN_ADRES <= len(adresler) <= MAX_ADRES:
        st.error(f"{MIN_ADRES} ile {MAX_ADRES} arasında teslimat adresi girin (şu an {len(adresler)}).")
    elif asiri:
        st.error(f"Bu adreslerin talebi tek bir aracın kapasitesinden ({kapasite} kg) büyük: {', '.join(asiri)}")
    elif en_az_arac > arac_sayisi:
        st.error(f"Toplam talep {sum(talepler)} kg; {kapasite} kg'lık araçlarla en az **{en_az_arac} araç** gerekir "
                 f"(şu an {arac_sayisi}).")
    else:
        # Sonucu session_state'e koyuyoruz: harita etkileşiminde sayfa yenilense de kaybolmasın.
        st.session_state["sonuc"] = rotayi_hesapla(
            depo.strip(), adresler, talepler, int(kapasite), int(arac_sayisi), servis_suresi, araci_azalt,
        )
        if st.session_state["sonuc"]:
            st.session_state["sonuc"]["girdi_imzasi"] = girdi_imzasi

sonuc = st.session_state.get("sonuc")
if not sonuc:
    st.info("👈 Soldan depo, adresler ve araç bilgilerini girip **Rotayı Hesapla**'ya basın. "
            "Samsun örnek verileri hazır.")
    st.stop()

# --- Uyarılar
if sonuc.get("girdi_imzasi") != girdi_imzasi:
    st.warning("✏️ Girdileri değiştirdiniz; aşağıdaki sonuç **önceki girdilere** ait. "
               "Güncellemek için **Rotayı Hesapla**'ya basın.")
if sonuc["bulunamayanlar"]:
    st.warning("Bulunamadığı için rotaya eklenmeyen adresler: " + ", ".join(sonuc["bulunamayanlar"]) +
               ". Daha açık yazmayı (ör. 'Mahalle, İlçe, İl') veya koordinat girmeyi deneyin.")
if sonuc.get("supheli_konumlar"):
    st.warning("📍 **Bu konumlar yanlış olabilir, kontrol edin:**\n\n- " + "\n- ".join(sonuc["supheli_konumlar"]) +
               "\n\nHaritada işarete dokunarak bulunan yeri görebilirsiniz.")
if sonuc["matris"]["kaynak"] == "tahmini":
    st.warning("Yol mesafesi servisine (OSRM) ulaşılamadı; mesafeler kuş uçuşu × "
               f"{mesafe.YOL_KATSAYISI} ile **tahmini** hesaplandı.")

# --- Tablolar (özet kartları da bunlardan beslenir)
mesafe_km, sure_dk = sonuc["matris"]["mesafe_km"], sonuc["matris"]["sure_dk"]
arac_tablosu = rapor.arac_ozeti(sonuc["optimize_rotalar"], sonuc["noktalar"], mesafe_km, sure_dk,
                                sonuc["kapasite"], sonuc["servis_suresi_dk"])
durak_tablosu = rapor.durak_tablosu(sonuc["optimize_rotalar"], sonuc["noktalar"], mesafe_km, sure_dk,
                                    sonuc["servis_suresi_dk"])

# --- Özet kartları
opt_km, opt_dk, opt_arac = sonuc["optimize"]
gir_km, gir_dk, gir_arac = sonuc["girilen"]
toplam_talep = sum(n["talep"] for n in sonuc["noktalar"])
k1, k2, k3, k4 = st.columns(4)
k1.metric("Toplam mesafe", f"{opt_km:.1f} km")
k2.metric("Kullanılan araç", f"{opt_arac} / {sonuc['arac_sayisi']}")
k3.metric("Ortalama doluluk", f"%{toplam_talep / (opt_arac * sonuc['kapasite']) * 100:.0f}",
          help="Toplam yük ÷ (kullanılan araç × kapasite)")
k4.metric("En uzun tur", sure_metni(arac_tablosu["Süre (dk)"].max()),
          help="Araçlar aynı anda yola çıkarsa son aracın depoya dönüş süresi (sürüş + teslim)")

# --- Karşılaştırma kutusu
tasarruf = optimizasyon.tasarruf_yuzdesi(gir_km, opt_km)
st.success(
    f"📊 **Girilen sırayla gitseydin {gir_km:.1f} km** ({gir_arac} sefer: adresler sırayla yüklenir, araç dolunca "
    f"depoya dönülür), **optimize plan {opt_km:.1f} km** ({opt_arac} araç) → **tasarruf %{tasarruf:.1f}** "
    f"({gir_km - opt_km:.1f} km, toplam araç süresinde yaklaşık {sure_metni(max(gir_dk - opt_dk, 0))} daha az)."
)

# --- Harita ve tablolar
sol, sag = st.columns([3, 2])
with sol:
    st.subheader("🗺️ Rota haritası")
    st_folium(harita.harita_olustur(sonuc), height=520, use_container_width=True, returned_objects=[])
with sag:
    st.subheader("🚛 Araçlar")
    st.dataframe(arac_tablosu, hide_index=True, width="stretch")
    st.subheader("📋 Durak sırası")
    st.dataframe(durak_tablosu.drop(columns=["Enlem", "Boylam"]), hide_index=True, width="stretch")

# --- Excel indirme
ozet = {
    "Depo": sonuc["noktalar"][0]["adres"],
    "Teslimat durağı sayısı": len(sonuc["noktalar"]) - 1,
    "Toplam talep (kg)": toplam_talep,
    "Araç kapasitesi (kg)": sonuc["kapasite"],
    "Kullanılan araç": opt_arac,
    "Planlama önceliği": "Önce araç sayısı, sonra km" if sonuc["araci_azalt"] else "Yalnızca toplam km",
    "Optimize plan (km)": round(opt_km, 2),
    "Optimize plan toplam araç süresi (dk)": round(opt_dk, 1),
    "Girilen sıra (km)": round(gir_km, 2),
    "Girilen sıra sefer sayısı": gir_arac,
    "Girilen sıra toplam araç süresi (dk)": round(gir_dk, 1),
    "Tasarruf (%)": round(tasarruf, 1),
    "Durak başı teslim süresi (dk)": sonuc["servis_suresi_dk"],
    "Mesafe kaynağı": "OSRM (gerçek yol)" if sonuc["matris"]["kaynak"] == "osrm" else "Tahmini (kuş uçuşu × katsayı)",
}
st.download_button(
    "⬇️ Sonucu Excel olarak indir",
    data=rapor.excel_olustur(ozet, {"Araçlar": arac_tablosu, "Durak Sırası": durak_tablosu}),
    file_name="teslimat_rotasi.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Tıklayınca sayfa yeniden çalışmasın: yoksa dosya yeniden üretilir ve
    # iPhone Safari eski bağlantıyı istediği için indirme "failed" olur.
    on_click="ignore",
)

# --- Bulunan konumlar: "İsim (enlem, boylam)" biçiminde kopyalanabilir liste.
# Bu satırlar adres tablosuna aynen yapıştırılabilir; o zaman konum servisine hiç gidilmez.
with st.expander("📍 Bulunan konumlar (koordinatlı, kopyalanabilir)"):
    satirlar = []
    for i, n in enumerate(sonuc["noktalar"]):
        isim = n["adres"]
        if geocoding.koordinat_metni_coz(isim):  # yalnızca koordinat girilmişse okunur bir ad ver
            isim = "Depo" if i == 0 else f"Durak {i}"
        satirlar.append(f"{isim} ({n['enlem']:.6f}, {n['boylam']:.6f})")
    st.caption("İlk satır depo. Sağ üstteki simgeyle kopyalayabilirsiniz.")
    st.code("\n".join(satirlar), language=None)
