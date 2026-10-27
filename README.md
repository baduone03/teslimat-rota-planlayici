# 🚚 Teslimat Rota Planlayıcı

![Testler](https://github.com/baduone03/teslimat-rota-planlayici/actions/workflows/testler.yml/badge.svg)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://teslimat-rota-planlayici.streamlit.app)

Bir depodan çıkıp **3–15 teslimat adresine** uğrayan ve depoya geri dönen **en kısa rotayı** hesaplayan web uygulaması.
Python + Streamlit ile yazıldı; **tamamen ücretsiz** servisler kullanır, **API anahtarı gerekmez**.

🔗 **Canlı demo:** [teslimat-rota-planlayici.streamlit.app](https://teslimat-rota-planlayici.streamlit.app)

## 📸 Ekran görüntüsü

![Uygulama ekran görüntüsü](docs/ekran-goruntusu.png)

## 🎯 Ne işe yarar?

Kurye veya dağıtım aracının adresleri **yazıldığı sırayla** gezmesi çoğu zaman gereksiz kilometre demektir.
Bu uygulama:

- Adresleri haritada bulur,
- Noktalar arasındaki **gerçek yol mesafelerini** hesaplar,
- **En kısa ziyaret sırasını** bulur,
- Sonucu haritada numaralı duraklarla, tabloda ve Excel dosyasında verir,
- "Girilen sırayla gitseydin **X km**, optimize rota **Y km**, tasarruf **%Z**" karşılaştırmasıyla kazancı gösterir.

Samsun örneğinde (Tekkeköy deposu, 8 mahalle) adresleri yazıldığı sırayla gezmek **126,0 km**, optimize rota ise **63,8 km**: **%49,4 tasarruf** (yaklaşık 1 saat daha az yol).

## ⚙️ Nasıl çalışır? (adım adım mantık)

```
Adresler ──► 1. Geocoding ──► 2. Mesafe matrisi ──► 3. Optimizasyon ──► 4. Sonuç
            (Nominatim)       (OSRM)                (OR-Tools)           (harita, tablo, Excel)
```

**1. Adres → koordinat (`geocoding.py`)**
"Körfez Mahallesi, Atakum, Samsun" gibi bir metni OpenStreetMap **Nominatim** servisiyle enlem/boylama çeviririz.
Servisin kullanım kurallarına uyarız: her istekte uygulamayı tanıtan bir **User-Agent** gönderilir, **saniyede en fazla 1 istek** atılır ve sonuçlar **önbelleğe** (bellek + JSON dosyası) alınır; aynı adres ikinci kez sorulmaz.

**2. Mesafe matrisi (`mesafe.py`)**
N nokta için N×N'lik bir tablo oluştururuz: `matris[i][j]` = i noktasından j noktasına **gerçek yol mesafesi** (km) ve **süresi** (dk).
Bunu **OSRM** `/table` servisi tek istekte verir. Tek yönlü yollar yüzünden A→B ile B→A farklı olabilir; model bunu doğal olarak destekler.
OSRM'e ulaşılamazsa uygulama durmaz: kuş uçuşu mesafe (Haversine formülü) × 1,3 yol katsayısıyla **tahmini** değer kullanır ve ekranda uyarır.

**3. En kısa sıra (`optimizasyon.py`)**
Bu, lojistikte meşhur **Gezgin Satıcı Problemi**dir (TSP). 15 adreste olası sıra sayısı 15! ≈ **1,3 trilyon** olduğundan hepsini denemek pratik değildir.
Google **OR-Tools** önce hızlı bir başlangıç çözümü kurar (*Path Cheapest Arc*: her adımda en ucuz bağlantıyı seç), sonra *Guided Local Search* ile bu rotayı 2 saniye boyunca iyileştirir.
Küçük örneklerde sonucun, tüm olasılıkları deneyen kaba kuvvet yöntemiyle **aynı optimumu** bulduğu testlerle doğrulanmıştır.

**4. Sonuç (`app.py`, `rapor.py`)**
- **folium** haritasında depo (kırmızı **D**) ve sıra numaralı duraklar, OSRM'den gelen gerçek yol çizgisi
- Durak sırası tablosu: her bacağın km/dk değeri ve kümülatif toplamlar
- Toplam km ve tahmini süre (sürüş + durak başı teslim süresi)
- Girilen sıra ile optimize rotanın karşılaştırması
- İki sayfalı (Özet + Durak Sırası) **Excel** indirme

## 📁 Proje yapısı

| Dosya | Görevi |
|---|---|
| `app.py` | Streamlit arayüzü; diğer modülleri sırayla çağırır |
| `geocoding.py` | Adres → koordinat (Nominatim), hız sınırı, önbellek |
| `mesafe.py` | OSRM mesafe/süre matrisi, rota çizgisi, çevrimdışı tahmin |
| `optimizasyon.py` | OR-Tools ile en kısa tur, rota uzunluğu, tasarruf hesabı |
| `rapor.py` | Durak tablosu ve Excel dosyası |
| `ornek_veriler.py` | Hazır Samsun depo/adresleri ve yedek koordinatlar |
| `tests/` | pytest testleri (ağ çağrıları taklit edilir, internetsiz çalışır) |

## 💻 Kurulum (kendi bilgisayarında)

Gereksinim: **Python 3.10+**

```bash
git clone https://github.com/baduone03/teslimat-rota-planlayici.git
cd teslimat-rota-planlayici

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır. Soldaki örnek adreslerle doğrudan **Rotayı Hesapla**'ya basabilirsiniz.

**Testleri çalıştırmak için:**

```bash
pytest
```

## 🧰 Kullanılan teknolojiler (hepsi ücretsiz)

| Teknoloji | Kullanım |
|---|---|
| [Streamlit](https://streamlit.io) | Web arayüzü |
| [OpenStreetMap Nominatim](https://nominatim.org) | Adres → koordinat |
| [OSRM](https://project-osrm.org) | Gerçek yol mesafesi, süre ve rota çizgisi |
| [Google OR-Tools](https://developers.google.com/optimization) | Rota optimizasyonu (TSP) |
| [folium](https://python-visualization.github.io/folium/) | Etkileşimli harita |
| pandas + openpyxl | Tablo ve Excel çıktısı |

## ⚠️ Bilinen sınırlar ve geliştirme fikirleri

- Nominatim ve OSRM'in **ücretsiz demo sunucuları** kullanılıyor; yoğun/ticari kullanım için kendi sunucunuzu kurmanız gerekir.
- Süreler **serbest akış** trafiğine göredir; anlık trafik dahil değildir.
- Tek araç vardır. OR-Tools'un desteklediği şu özellikler kolayca eklenebilir:
  - **Araç kapasitesi** (CVRP — desi/kg sınırı)
  - **Zaman pencereleri** (VRPTW — "müşteri 10:00–12:00 arası")
  - **Birden fazla araç** ve araç başı maksimum mesai süresi
- Adresler CSV/Excel'den toplu yüklenebilir.

## 🚀 Streamlit Community Cloud'a ücretsiz yayınlama

1. Kodun GitHub'da **public** (herkese açık) bir repoda olduğundan emin olun.
2. [share.streamlit.io](https://share.streamlit.io) adresine gidin ve **"Continue with GitHub"** ile giriş yapın; istenen izinleri onaylayın.
3. Sağ üstten **"Create app"** → **"Deploy a public app from GitHub"** seçin.
4. Formu doldurun:
   - **Repository:** `baduone03/teslimat-rota-planlayici`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** isterseniz `teslimat-rota-planlayici` gibi akılda kalıcı bir ad yazın
5. **Advanced settings** → **Python version** olarak **3.12** veya **3.13** seçin.
6. **Deploy** butonuna basın. İlk kurulum `requirements.txt`'teki paketleri yüklediği için birkaç dakika sürer.
7. Uygulama açılınca örnek adreslerle **Rotayı Hesapla**'yı deneyin ve linki README'ye ekleyin.

**Notlar:**
- `main` dalına her push yaptığınızda uygulama otomatik güncellenir.
- Ücretsiz planda uygulama bir süre kullanılmazsa uyku moduna geçer; ilk ziyaretçi "Yes, get this app back up" butonuyla uyandırır (~30 sn).
- Hiçbir API anahtarı veya "secret" tanımlamanız gerekmez.

## 📄 Lisans

MIT
