"""Uygulama açıldığında hazır gelen Samsun örnek verileri.

Adresler bilerek "karışık" sırada yazıldı: böylece optimize rotanın
girilen sıraya göre ne kadar tasarruf sağladığı net görülür.
"""

ORNEK_DEPO = "Tekkeköy, Samsun"

ORNEK_ADRESLER = [
    "Kurupelit, Atakum, Samsun",
    "Yaşardoğu Mahallesi, Canik, Samsun",
    "Pazar Mahallesi, İlkadım, Samsun",
    "Körfez Mahallesi, Atakum, Samsun",
    "Hacı Osman Mahallesi, Canik, Samsun",
    "Derebahçe Mahallesi, İlkadım, Samsun",
    "Mimar Sinan Mahallesi, Atakum, Samsun",
    "Kılıçdede Mahallesi, İlkadım, Samsun",
]

# Her adresin teslimat miktarı (kg). Toplam 1580 kg; 800 kg'lık araçla en az 2 araç gerekir.
ORNEK_TALEPLER = [180, 250, 120, 300, 200, 150, 220, 160]
ORNEK_KAPASITE_KG = 800
ORNEK_ARAC_SAYISI = 3

# Nominatim'e ulaşılamazsa (internet yok, servis yoğun vb.) demo yine
# çalışsın diye örnek adreslerin YAKLAŞIK koordinatları (enlem, boylam).
# Normal durumda bu değerler kullanılmaz; gerçek sonuç Nominatim'den gelir.
YEDEK_KOORDINATLAR = {
    "Tekkeköy, Samsun": (41.2125, 36.4565),
    "Kurupelit, Atakum, Samsun": (41.3640, 36.2200),
    "Yaşardoğu Mahallesi, Canik, Samsun": (41.2650, 36.3550),
    "Pazar Mahallesi, İlkadım, Samsun": (41.2900, 36.3330),
    "Körfez Mahallesi, Atakum, Samsun": (41.3230, 36.2870),
    "Hacı Osman Mahallesi, Canik, Samsun": (41.2600, 36.3700),
    "Derebahçe Mahallesi, İlkadım, Samsun": (41.2810, 36.3200),
    "Mimar Sinan Mahallesi, Atakum, Samsun": (41.3340, 36.2660),
    "Kılıçdede Mahallesi, İlkadım, Samsun": (41.2880, 36.3270),
}
