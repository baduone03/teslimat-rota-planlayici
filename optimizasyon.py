"""En kısa teslimat rotalarını bulan modül (Google OR-Tools).

Tek araç, kapasite yok → "Gezgin Satıcı Problemi" (TSP):
  Depodan çık, her adrese tam bir kez uğra, depoya dön; toplam mesafe en az olsun.
Birden fazla araç + kapasite → "Kapasite Kısıtlı Araç Rotalama Problemi" (CVRP):
  Adresleri araçlara paylaştır; hiçbir aracın yükü kapasitesini aşmasın; toplam km en az olsun.

15 adreste olası sıra sayısı 15! ≈ 1,3 trilyondur; hepsini denemek pratik değil.
OR-Tools önce hızlı bir başlangıç çözümü kurar (en yakın/ucuz bağlantıyı seç),
sonra "Guided Local Search" ile bu çözümü verilen süre boyunca iyileştirir.
"""

import math

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def rota_uzunlugu(matris, rota):
    """Bir rotanın (düğüm sırası) matrise göre toplam uzunluğu."""
    return sum(matris[rota[i]][rota[i + 1]] for i in range(len(rota) - 1))


def toplam_uzunluk(matris, rotalar):
    """Birden fazla aracın rotalarının toplam uzunluğu."""
    return sum(rota_uzunlugu(matris, rota) for rota in rotalar)


def girilen_sira_rotasi(nokta_sayisi, depo=0):
    """Kullanıcının yazdığı sırayla gidilseydi: depo → 1 → 2 → ... → depo."""
    return [depo] + [i for i in range(nokta_sayisi) if i != depo] + [depo]


def girilen_sira_rotalari(talepler, kapasite=None, depo=0):
    """Elle planlama taklidi: adresler yazıldığı sırayla araca yüklenir,
    sıradaki adres sığmazsa araç depoya döner ve yeni bir araç başlar.

    talepler: her düğümün talebi (depo dahil, depo talebi 0).
    """
    rotalar, mevcut, yuk = [], [depo], 0
    for dugum in range(len(talepler)):
        if dugum == depo:
            continue
        if kapasite is not None and yuk + talepler[dugum] > kapasite and len(mevcut) > 1:
            rotalar.append(mevcut + [depo])
            mevcut, yuk = [depo], 0
        mevcut.append(dugum)
        yuk += talepler[dugum]
    rotalar.append(mevcut + [depo])
    return rotalar


def gereken_en_az_arac(talepler, kapasite):
    """Toplam talebe göre en az kaç araç gerekir (alt sınır)."""
    return max(1, math.ceil(sum(talepler) / kapasite))


def tasarruf_yuzdesi(eski, yeni):
    """Eski değere göre yüzde kaç azalma olduğu."""
    if eski <= 0:
        return 0.0
    return (eski - yeni) / eski * 100


def kapasiteli_rotalar(mesafe_km, talepler=None, kapasite=None, arac_sayisi=1, depo=0, sure_limiti_sn=2,
                       araci_azalt=False):
    """Mesafe matrisine göre araç rotalarını bulur (CVRP).

    mesafe_km: NxN liste, mesafe_km[i][j] = i'den j'ye yol mesafesi (km).
               Tek yönlü yollar yüzünden simetrik olmayabilir; sorun değil.
    talepler: her düğümün talebi (kg, tam sayı; depo için 0). None → kapasite kısıtı yok.
    kapasite: araç başı kapasite (kg). None → kapasite kısıtı yok.
    araci_azalt: True → önce kullanılan araç sayısı, sonra km en aza indirilir.
    Dönüş: kullanılan her araç için [depo, ..., depo] listesi. Uygun çözüm yoksa None.
    """
    n = len(mesafe_km)
    if n <= 2:
        return [girilen_sira_rotasi(n, depo)]

    # OR-Tools tam sayı ister: km'yi metreye çevirip yuvarlıyoruz.
    matris_m = [[int(round(d * 1000)) for d in satir] for satir in mesafe_km]

    # 1) Düğüm yöneticisi: n nokta, arac_sayisi araç, hepsi depodan başlar/biter.
    yonetici = pywrapcp.RoutingIndexManager(n, arac_sayisi, depo)
    model = pywrapcp.RoutingModel(yonetici)

    # 2) Maliyet fonksiyonu: iki nokta arası mesafe.
    def mesafe_fonksiyonu(from_index, to_index):
        return matris_m[yonetici.IndexToNode(from_index)][yonetici.IndexToNode(to_index)]

    maliyet_id = model.RegisterTransitCallback(mesafe_fonksiyonu)
    model.SetArcCostEvaluatorOfAllVehicles(maliyet_id)

    # 3) Kapasite kısıtı: her araçta taşınan toplam yük ≤ kapasite.
    #    "Boyut" (dimension) OR-Tools'ta rota boyunca biriken bir değerdir; burada yük birikiyor.
    if talepler is not None and kapasite is not None:
        def talep_fonksiyonu(from_index):
            return int(talepler[yonetici.IndexToNode(from_index)])

        talep_id = model.RegisterUnaryTransitCallback(talep_fonksiyonu)
        model.AddDimensionWithVehicleCapacity(
            talep_id,
            0,  # bekleme payı yok
            [int(kapasite)] * arac_sayisi,  # her aracın kapasitesi
            True,  # yük depoda sıfırdan başlar
            "Kapasite",
        )

    # 4) Araç sayısını önceliklendirme: her kullanılan araca, olası tüm km'lerin toplamından büyük
    #    bir "sabit maliyet" eklenir. Böylece 1 araç eksiltmek her zaman km kazancından daha değerli olur.
    if araci_azalt:
        model.SetFixedCostOfAllVehicles(sum(map(sum, matris_m)) + 1)

    # 5) Arama stratejisi: hızlı başlangıç + yerel arama ile iyileştirme.
    parametreler = pywrapcp.DefaultRoutingSearchParameters()
    parametreler.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parametreler.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parametreler.time_limit.FromSeconds(sure_limiti_sn)

    cozum = model.SolveWithParameters(parametreler)
    if cozum is None:
        return None

    # 6) Çözümü araç başına düğüm listesine çevir; hiç durağı olmayan araçları atla.
    rotalar = []
    for arac in range(arac_sayisi):
        rota = []
        index = model.Start(arac)
        while not model.IsEnd(index):
            rota.append(yonetici.IndexToNode(index))
            index = cozum.Value(model.NextVar(index))
        rota.append(yonetici.IndexToNode(index))
        if len(rota) > 2:
            rotalar.append(rota)
    return rotalar


def en_kisa_rota(mesafe_km, depo=0, sure_limiti_sn=2):
    """Tek araç, kapasite yok: en kısa tur (TSP). Dönüş: [depo, ..., depo]."""
    rotalar = kapasiteli_rotalar(mesafe_km, depo=depo, sure_limiti_sn=sure_limiti_sn)
    return rotalar[0] if rotalar else girilen_sira_rotasi(len(mesafe_km), depo)
