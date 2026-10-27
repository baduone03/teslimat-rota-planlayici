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


def girilen_sira_filo(talepler, kapasiteler, depo=0):
    """Farklı kapasiteli filo için elle planlama taklidi.

    Araçlar filodaki sırayla kullanılır (liste bitince başa dönülür = ikinci sefer). Adresler yazıldığı sırayla
    o anki araca yüklenir; sıradaki adres sığmazsa araç depoya döner ve sıradaki araç başlar.
    Boş araca bile sığmayan bir yük gelirse o araç atlanır (yük en büyük araca sığıyor varsayılır).
    Dönüş: [(arac_index, rota), ...]
    """
    seferler, arac, mevcut, yuk = [], 0, [depo], 0
    for dugum in range(len(talepler)):
        if dugum == depo:
            continue
        while yuk + talepler[dugum] > kapasiteler[arac]:
            if len(mevcut) > 1:
                seferler.append((arac, mevcut + [depo]))
            arac, mevcut, yuk = (arac + 1) % len(kapasiteler), [depo], 0
        mevcut.append(dugum)
        yuk += talepler[dugum]
    seferler.append((arac, mevcut + [depo]))
    return seferler


def filoyu_ac(filo):
    """[(tip, kapasite, adet), ...] satırlarını tek tek araçlara açar.
    Aynı tipten birden fazla araç varsa numaralanır: Kamyon, Kamyonet 1, Kamyonet 2.
    Dönüş: (araç adları, kapasiteler)"""
    toplam = {}
    for tip, _, adet in filo:
        toplam[tip] = toplam.get(tip, 0) + adet
    adlar, kapasiteler, sayac = [], [], {}
    for tip, kapasite, adet in filo:
        for _ in range(adet):
            sayac[tip] = sayac.get(tip, 0) + 1
            adlar.append(tip if toplam[tip] == 1 else f"{tip} {sayac[tip]}")
            kapasiteler.append(kapasite)
    return adlar, kapasiteler


def esdeger_araclari_sirala(plan, arac_turleri):
    """Aynı tip ve kapasitedeki araçlar birbirinin aynısıdır; çözücü bunlardan rastgele birini seçebilir
    (ör. "Kamyonet 2" kullanılıp "Kamyonet 1" boş kalır). Kullanılanlara aynı türün en küçük numaralarını verir.
    plan: [(arac_index, rota), ...]; arac_turleri: her araç için (tip, kapasite)."""
    alinan, sonuc = set(), []
    for arac, rota in plan:
        yeni = next(i for i, tur in enumerate(arac_turleri) if tur == arac_turleri[arac] and i not in alinan)
        alinan.add(yeni)
        sonuc.append((yeni, rota))
    return sonuc


def filo_hatalari(talepler, kapasiteler, adlar=None):
    """Planlamaya başlamadan önce filonun yükü taşıyıp taşıyamayacağını kontrol eder.
    talepler: yalnızca durakların talepleri (depo hariç). Dönüş: hata metinleri listesi (boşsa sorun yok)."""
    adlar = adlar or [f"Durak {i}" for i in range(1, len(talepler) + 1)]
    if not kapasiteler:
        return ["Filoda en az bir araç olmalı."]
    hatalar = []
    en_buyuk = max(kapasiteler)
    sigmayanlar = [ad for ad, t in zip(adlar, talepler, strict=True) if t > en_buyuk]
    if sigmayanlar:
        hatalar.append(f"Bu adreslerin yükü en büyük aracın kapasitesinden ({en_buyuk} kg) fazla: "
                       + ", ".join(sigmayanlar))
    if sum(talepler) > sum(kapasiteler):
        hatalar.append(f"Toplam yük {sum(talepler)} kg, filonun toplam kapasitesi {sum(kapasiteler)} kg. "
                       "Araç ekleyin veya kapasiteyi artırın.")
    return hatalar


def gereken_en_az_arac(talepler, kapasite):
    """Toplam talebe göre en az kaç araç gerekir (alt sınır)."""
    return max(1, math.ceil(sum(talepler) / kapasite))


def tasarruf_yuzdesi(eski, yeni):
    """Eski değere göre yüzde kaç azalma olduğu."""
    if eski <= 0:
        return 0.0
    return (eski - yeni) / eski * 100


def filo_rotalari(mesafe_km, talepler=None, kapasiteler=None, arac_sayisi=None, depo=0, sure_limiti_sn=2,
                  araci_azalt=False):
    """Mesafe matrisine göre araç rotalarını bulur (CVRP, farklı kapasiteli araçlarla da).

    mesafe_km: NxN liste, mesafe_km[i][j] = i'den j'ye yol mesafesi (km).
               Tek yönlü yollar yüzünden simetrik olmayabilir; sorun değil.
    talepler: her düğümün talebi (kg, tam sayı; depo için 0). None → kapasite kısıtı yok.
    kapasiteler: her aracın kapasitesi, ör. [1000, 600, 600]. None → kapasite kısıtı yok (arac_sayisi kadar araç).
    araci_azalt: True → önce kullanılan araç sayısı, sonra km en aza indirilir.
    Dönüş: kullanılan her araç için (arac_index, [depo, ..., depo]). Uygun çözüm yoksa None.
    """
    arac_sayisi = len(kapasiteler) if kapasiteler else (arac_sayisi or 1)
    n = len(mesafe_km)
    if n <= 2:
        return [(0, girilen_sira_rotasi(n, depo))]

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

    # 3) Kapasite kısıtı: her araçta taşınan toplam yük ≤ o aracın kapasitesi.
    #    "Boyut" (dimension) OR-Tools'ta rota boyunca biriken bir değerdir; burada yük birikiyor.
    #    Kapasiteler araç başına ayrı liste olarak verildiği için kamyon + kamyonet gibi karışık filo desteklenir.
    if talepler is not None and kapasiteler:
        def talep_fonksiyonu(from_index):
            return int(talepler[yonetici.IndexToNode(from_index)])

        talep_id = model.RegisterUnaryTransitCallback(talep_fonksiyonu)
        model.AddDimensionWithVehicleCapacity(
            talep_id,
            0,  # bekleme payı yok
            [int(k) for k in kapasiteler],  # her aracın kendi kapasitesi
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
    parametreler.time_limit.FromMilliseconds(int(sure_limiti_sn * 1000))  # 0.3 sn gibi kesirli süreler de olur

    cozum = model.SolveWithParameters(parametreler)
    if cozum is None:
        return None

    # 6) Çözümü araç başına düğüm listesine çevir; hiç durağı olmayan araçları atla.
    sonuc = []
    for arac in range(arac_sayisi):
        rota = []
        index = model.Start(arac)
        while not model.IsEnd(index):
            rota.append(yonetici.IndexToNode(index))
            index = cozum.Value(model.NextVar(index))
        rota.append(yonetici.IndexToNode(index))
        if len(rota) > 2:
            sonuc.append((arac, rota))
    return sonuc


def kapasiteli_rotalar(mesafe_km, talepler=None, kapasite=None, arac_sayisi=1, depo=0, sure_limiti_sn=2,
                       araci_azalt=False):
    """Tüm araçlar aynı kapasitedeyken kısa yol: yalnızca rotaları döner (hangi araç olduğu önemsiz)."""
    kapasiteler = [kapasite] * arac_sayisi if (talepler is not None and kapasite is not None) else None
    sonuc = filo_rotalari(mesafe_km, talepler, kapasiteler, arac_sayisi, depo, sure_limiti_sn, araci_azalt)
    return None if sonuc is None else [rota for _, rota in sonuc]


def en_kisa_rota(mesafe_km, depo=0, sure_limiti_sn=2):
    """Tek araç, kapasite yok: en kısa tur (TSP). Dönüş: [depo, ..., depo]."""
    rotalar = kapasiteli_rotalar(mesafe_km, depo=depo, sure_limiti_sn=sure_limiti_sn)
    return rotalar[0] if rotalar else girilen_sira_rotasi(len(mesafe_km), depo)
