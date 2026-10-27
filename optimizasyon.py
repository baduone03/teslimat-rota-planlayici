"""En kısa teslimat sırasını bulan modül (Google OR-Tools).

Problem, "Gezgin Satıcı Problemi"dir (TSP - Traveling Salesman Problem):
Depodan çık, her adrese tam bir kez uğra, depoya dön; toplam mesafe en az olsun.

15 adreste olası sıra sayısı 15! ≈ 1,3 trilyondur; hepsini denemek pratik değil.
OR-Tools önce hızlı bir başlangıç çözümü kurar (en yakın/ucuz bağlantıyı seç),
sonra "Guided Local Search" ile bu çözümü verilen süre boyunca iyileştirir.
"""

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def rota_uzunlugu(matris, rota):
    """Bir rotanın (düğüm sırası) matrise göre toplam uzunluğu."""
    return sum(matris[rota[i]][rota[i + 1]] for i in range(len(rota) - 1))


def girilen_sira_rotasi(nokta_sayisi, depo=0):
    """Kullanıcının yazdığı sırayla gidilseydi: depo → 1 → 2 → ... → depo."""
    return [depo] + [i for i in range(nokta_sayisi) if i != depo] + [depo]


def tasarruf_yuzdesi(eski, yeni):
    """Eski değere göre yüzde kaç azalma olduğu."""
    if eski <= 0:
        return 0.0
    return (eski - yeni) / eski * 100


def en_kisa_rota(mesafe_km, depo=0, sure_limiti_sn=2):
    """Mesafe matrisine göre en kısa turu bulur.

    mesafe_km: NxN liste, mesafe_km[i][j] = i'den j'ye yol mesafesi (km).
               Tek yönlü yollar yüzünden simetrik olmayabilir; sorun değil.
    Dönüş: [depo, ..., depo] şeklinde düğüm sırası.
    """
    n = len(mesafe_km)
    if n <= 2:
        return girilen_sira_rotasi(n, depo)

    # OR-Tools tam sayı ister: km'yi metreye çevirip yuvarlıyoruz.
    matris_m = [[int(round(d * 1000)) for d in satir] for satir in mesafe_km]

    # 1) Düğüm yöneticisi: n nokta, 1 araç, depo başlangıç/bitiş.
    yonetici = pywrapcp.RoutingIndexManager(n, 1, depo)
    model = pywrapcp.RoutingModel(yonetici)

    # 2) Maliyet fonksiyonu: iki nokta arası mesafe.
    def mesafe_fonksiyonu(from_index, to_index):
        return matris_m[yonetici.IndexToNode(from_index)][yonetici.IndexToNode(to_index)]

    maliyet_id = model.RegisterTransitCallback(mesafe_fonksiyonu)
    model.SetArcCostEvaluatorOfAllVehicles(maliyet_id)

    # 3) Arama stratejisi: hızlı başlangıç + yerel arama ile iyileştirme.
    parametreler = pywrapcp.DefaultRoutingSearchParameters()
    parametreler.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parametreler.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parametreler.time_limit.FromSeconds(sure_limiti_sn)

    cozum = model.SolveWithParameters(parametreler)
    if cozum is None:
        return girilen_sira_rotasi(n, depo)

    # 4) Çözümü düğüm listesine çevir.
    rota = []
    index = model.Start(0)
    while not model.IsEnd(index):
        rota.append(yonetici.IndexToNode(index))
        index = cozum.Value(model.NextVar(index))
    rota.append(yonetici.IndexToNode(index))
    return rota
