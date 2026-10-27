"""Uygulama açıldığında hazır gelen Samsun örnek verileri.

Tüm konumlar "İsim (enlem, boylam)" biçiminde koordinatlıdır: depo, Kurupelit Sahil, Körfez
Muhtarlığı ve Yaşar Doğu Spor Salonu Google Haritalar'dan; diğer duraklar Nominatim'in bulduğu
konumlardan alındı. Hepsi haritada gözle doğrulandı.
Böylece demo, konum servislerine hiç sormadan her açılışta aynı sonucu verir.

Adresler bilerek "karışık" sırada yazıldı: böylece optimize planın girilen
sıraya göre ne kadar tasarruf sağladığı net görülür.
"""

ORNEK_DEPO = "İlkadım Sanayi Sitesi (41.2767769, 36.3540910)"

ORNEK_ADRESLER = [
    "Kurupelit Sahil, Atakum, Samsun (41.361528, 36.233944)",
    "Yaşar Doğu Spor Salonu, Tekkeköy, Samsun (41.2262993, 36.4526196)",
    "Pazar Mahallesi, İlkadım, Samsun (41.295010, 36.331358)",
    "Körfez Mahallesi Muhtarlığı, Atakum, Samsun (41.360083, 36.233472)",
    "Derebahçe Mahallesi, İlkadım, Samsun (41.265636, 36.337348)",
    "Mimar Sinan Mahallesi, Atakum, Samsun (41.330907, 36.277384)",
    "Kılıçdede Mahallesi, İlkadım, Samsun (41.279967, 36.348052)",
]

# Her adresin teslimat miktarı (kg). Toplam 1380 kg; 800 kg'lık araçla en az 2 araç gerekir.
ORNEK_TALEPLER = [180, 250, 120, 300, 150, 220, 160]
ORNEK_KAPASITE_KG = 800
ORNEK_ARAC_SAYISI = 3
