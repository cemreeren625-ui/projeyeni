# Python standart kütüphane: dict içinde list biriktirmek için
from collections import defaultdict

# Tarih hesapları (deadline kontrolü vs.)
from datetime import date, timedelta

# Django: DB’den nesne bulma + template render + redirect
from django.shortcuts import get_object_or_404, render, redirect

# Django: sadece POST kabul eden view decorator
from django.views.decorators.http import require_POST

# DRF: generic API view sınıfları + HTTP status kodları
from rest_framework import generics, status

# DRF: fonksiyon tabanlı API view decorator
from rest_framework.decorators import api_view

# DRF: JSON response helper
from rest_framework.response import Response

# Proje modelleri
from .models import Sirket, Duzenleme, SirketObligation

# Serializer’lar (Model -> JSON)
from .serilestiriciler import SirketSerializer, DuzenlemeSerializer

# Django: JSON döndürmek için
from django.http import JsonResponse

# Django: belirli HTTP methodlarına izin vermek için
from django.views.decorators.http import require_http_methods


def hesapla_sirket_skoru(sirket: Sirket, obligations=None):
    """
    Bir şirket için uyum skorunu ve dashboard listelerini hesaplar.

    obligations parametresi:
    - None ise DB’den şirketin uygulanabilir yükümlülüklerini çeker.
    - Dışarıdan verilirse (prefetch / grouped list) o liste üzerinden hesaplar.
    """

    # obligations verilmediyse: DB’den çek (prefetch varsa onu kullan)
    if obligations is None:
        REL = "sirketobligation_set"  # related_name verdiysen bunu değiştirmen gerekir

        # Django prefetch yaptıysa, prefetched cache içinde olur (performans için)
        cache = getattr(sirket, "_prefetched_objects_cache", {})

        # Prefetch varsa direkt ordan al
        if REL in cache:
            obligations = cache[REL]
        else:
            # Prefetch yoksa DB sorgusu
            obligations = list(
                SirketObligation.objects.filter(sirket=sirket, is_applicable=True)
                .select_related("duzenleme")  # her obligation'ın duzenleme FK'sini tek query’de çek
            )
    else:
        # dışarıdan gelen iterablesa listeye çevir (tek tip olsun)
        obligations = list(obligations)

    # Bugünün tarihi (deadline kıyasları için)
    today = date.today()

    # Skor başlangıcı 100
    score = 100

    # Açık yükümlülük sayısı
    open_count = 0

    # Gecikmiş yükümlülük sayısı (due_date < today)
    overdue_count = 0

    # TODO listesi (tamamlanmamış yükümlülükler)
    todo_items = []

    # Completed listesi (tamamlanmış yükümlülükler)
    completed_items = []

    # Etki tipine göre ceza puanları
    impact_penalties = {"zorunlu": 15, "risk": 10, "opsiyonel_tesvik": 5}

    # Risk seviyesine göre ceza puanları
    risk_penalties = {"low": 0, "medium": 3, "high": 7}

    # Şirketin tüm obligations’ları üzerinde dolaş
    for obl in obligations:
        reg = obl.duzenleme  # obligation'ın bağlı olduğu düzenleme

        # Eğer yükümlülük tamamlandıysa completed listesine ekle
        if obl.is_compliant:
            completed_items.append({
                "obligation_id": obl.id,
                "regulation_id": reg.id,
                "regulation_title": reg.title,
                "due_date": obl.due_date,
                "risk_level": obl.risk_level,
                "impact_type": reg.impact_type,
            })

            # Opsiyonel teşvik tamamlandıysa küçük bonus ver
            if reg.impact_type == "opsiyonel_tesvik":
                score += 5

            # completed için ceza hesaplamaya gerek yok
            continue

        # Buraya geldiysek: obligation açık (todo)
        open_count += 1

        # Etki tipinin cezası (yoksa 0)
        impact_pen = impact_penalties.get(reg.impact_type or "", 0)

        # Risk seviyesinin cezası (risk_level boşsa medium varsay)
        risk_pen = risk_penalties.get(obl.risk_level or "medium", 0)

        # Tarih bazlı ceza (gecikmiş/7 güne yakın)
        date_pen = 0
        if obl.due_date:
            # Gecikmişse
            if obl.due_date < today:
                overdue_count += 1
                date_pen = 10
            # 7 gün içinde yaklaşan deadline ise
            elif obl.due_date <= today + timedelta(days=7):
                date_pen = 5

        # Toplam cezayı skordan düş
        score -= (impact_pen + risk_pen + date_pen)

        # TODO listesine ekle
        todo_items.append({
            "obligation_id": obl.id,
            "regulation_id": reg.id,
            "regulation_title": reg.title,
            "due_date": obl.due_date,
            "risk_level": obl.risk_level,
            "impact_type": reg.impact_type,
        })

    # Skoru 0-100 aralığına sıkıştır
    score = max(0, min(100, score))

    # Toplam obligation sayısı
    total_obligations = len(obligations)

    # API’ların kullandığı standart sonuç sözlüğü
    return {
        "uyum_skoru": score,      # eski/alternatif alan adı
        "score": score,          # ana skor
        "stats": {
            "total_obligations": total_obligations,
            "open_obligations": open_count,
            "overdue_obligations": overdue_count,
        },
        "todo": todo_items,
        "completed": completed_items,
    }


def build_dashboard_payload(sirket: Sirket):
    """
    Hem HTML panel hem JSON API’nin ortak payload formatı.
    """
    sonuc = hesapla_sirket_skoru(sirket)

    return {
        "sirket": SirketSerializer(sirket).data,  # şirket bilgileri JSON
        "uyum_skoru": sonuc["score"],             # UI’da gösterilecek skor
        "stats": sonuc["stats"],                  # istatistikler
        "todo": sonuc["todo"],                    # yapılacaklar
        "completed": sonuc["completed"],          # tamamlananlar
    }


@require_http_methods(["GET"])
def Sirket_dashboard(request, pk):
    """
    Django view: GET /api/companies/<pk>/dashboard/
    JSON dashboard döndürür.
    """
    sirket = get_object_or_404(Sirket, pk=pk)      # şirket yoksa 404
    payload = build_dashboard_payload(sirket)      # ortak payload
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})  # Türkçe düzgün


@api_view(["PATCH"])
def obligation_status_api(request, pk):
    """
    DRF endpoint: PATCH /api/obligations/<pk>/status/
    Body: {"is_compliant": true/false}
    """
    obligation = get_object_or_404(SirketObligation, pk=pk)  # obligation yoksa 404

    # Body’den is_compliant al (gelmezse True varsayılmış)
    is_compliant = request.data.get("is_compliant", True)

    # DB’de güncelle
    obligation.is_compliant = bool(is_compliant)
    obligation.save()

    # Güncel dashboard’u geri döndür (frontend bir daha GET atmak zorunda kalmasın)
    return Response(build_dashboard_payload(obligation.sirket), status=status.HTTP_200_OK)


# /api/companies/  -> şirket listele + oluştur
class SirketListCreateView(generics.ListCreateAPIView):
    # Varsayılan query: tüm şirketleri id desc sırala
    queryset = Sirket.objects.all().order_by("-id")

    # Şirket serializer'ı (name, sector vs. döndüren)
    serializer_class = SirketSerializer

    def list(self, request, *args, **kwargs):
        """
        Şirket listesi endpoint'i:
        - ?sector=yazilim   → sektöre göre filtre
        - ?risky=true       → compliance_score < threshold olanları getir
        - ?threshold=70     → eşiği override et (default 80)

        ✅ Bu fonksiyon ayrıca her şirkete "compliance_score" alanı gömer
        (React CompaniesList.jsx bunu ekranda gösterir)
        """

        # 1) Temel query'yi al (Sirket.objects...)
        queryset = self.get_queryset()

        # 2) Query parametrelerini al
        sector = request.query_params.get("sector")
        risky = request.query_params.get("risky")
        threshold_param = request.query_params.get("threshold")

        # 3) Sektör filtresi (seçilmişse)
        if sector:
            queryset = queryset.filter(sector=sector)

        # 4) Performans: tüm seçili şirketlerin id'lerini al
        # (obligation'ları tek seferde çekebilmek için)
        sirket_ids = list(queryset.values_list("id", flat=True))

        # 5) Seçili şirketlere ait tüm obligations'ları tek query ile çek
        # (N+1 probleminden kaçınmak için)
        ob_qs = SirketObligation.objects.filter(
            sirket_id__in=sirket_ids,
            is_applicable=True,
        ).select_related("duzenleme")  # duzenleme'yi de yanına al

        # 6) obligations'ları şirket bazında grupla: { company_id: [ob1, ob2, ...] }
        by_company = defaultdict(list)
        for ob in ob_qs:
            by_company[ob.sirket_id].append(ob)

        # 7) Şirket listesini serializer ile JSON'a çevir
        serializer = self.get_serializer(queryset, many=True)
        data = list(serializer.data)  # dict listesi

        # 8) Her şirket için skor hesapla (hazır grouped obligations ile)
        score_map = {}
        for s in queryset:
            sonuc = hesapla_sirket_skoru(s, obligations=by_company.get(s.id, []))
            score_map[s.id] = sonuc["score"]  # 0-100 arası skor

        # 9) Serializer'dan gelen her şirkete compliance_score alanını ekle
        for item in data:
            cid = item.get("id")
            item["compliance_score"] = score_map.get(cid, 100)  # obligations yoksa default 100

        # 10) Eğer risky=true ise eşik altını filtrele
        if risky == "true":
            try:
                threshold = int(threshold_param) if threshold_param is not None else 80
            except ValueError:
                threshold = 80

            # sadece compliance_score < threshold olanları bırak
            data = [item for item in data if item["compliance_score"] < threshold]

        # 11) JSON response döndür
        return Response(data)



# /api/companies/<id>/  -> şirket getir/güncelle/sil
class SirketDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sirket.objects.all()
    serializer_class = SirketSerializer


# /api/Duzenlemes/ -> mevzuat listele/oluştur
class DuzenlemeListCreateView(generics.ListCreateAPIView):
    queryset = Duzenleme.objects.all().order_by("-publish_date")
    serializer_class = DuzenlemeSerializer


# /api/Duzenlemes/<id>/ -> mevzuat getir/güncelle/sil
class DuzenlemeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Duzenleme.objects.all()
    serializer_class = DuzenlemeSerializer


def sirket_dashboard_page(request, pk):
    """
    Django HTML panel:
    /api/companies/<id>/dashboard-page/
    """
    sirket = get_object_or_404(Sirket, pk=pk)  # şirketi bul
    sonuc = hesapla_sirket_skoru(sirket)       # skoru hesapla

    # Template'e gidecek context
    context = {
        "sirket": sirket,
        "compliance_score": sonuc["score"],
        "stats": sonuc["stats"],
        "todo": sonuc["todo"],
        "completed": sonuc["completed"],
    }

    return render(request, "sirket_dashboard.html", context)


def sirket_list_page(request):
    """
    Django HTML liste ekranı:
    /api/sirket-list/ (örnek)
    sector filtresi destekli.
    """
    selected_sector = request.GET.get("sector")

    sirket_qs = Sirket.objects.all().order_by("name")
    if selected_sector:
        sirket_qs = sirket_qs.filter(sector=selected_sector)

    # N+1 engellemek için: şirket id’lerini al
    sirket_ids = list(sirket_qs.values_list("id", flat=True))

    # Tüm obligations’ları tek seferde çek
    ob_qs = SirketObligation.objects.filter(
        sirket_id__in=sirket_ids,
        is_applicable=True,
    ).select_related("duzenleme")

    # company_id -> obligations listesi
    by_company = defaultdict(list)
    for ob in ob_qs:
        by_company[ob.sirket_id].append(ob)

    # Her şirket için skor hesapla (DB’ye tekrar gitmeden)
    sirketler = []
    for s in sirket_qs:
        sonuc = hesapla_sirket_skoru(s, obligations=by_company.get(s.id, []))
        sirketler.append({"sirket": s, "score": sonuc["score"]})

    context = {
        "sirketler": sirketler,
        "selected_sector": selected_sector,
        "sector_choices": Sirket.SECTOR_CHOICES,
    }
    return render(request, "sirket_list.html", context)


def sirket_riskli_list_page(request):
    """
    Django HTML riskli şirketler sayfası.
    URL örnek: /api/companies-risky/
    ?max_score=70 ile eşik değişebilir.
    """
    try:
        threshold = int(request.GET.get("max_score", "80"))
    except ValueError:
        threshold = 80

    sirket_qs = Sirket.objects.all().order_by("name")

    # Eşik altı şirketleri topla
    sirketler = []
    for s in sirket_qs:
        sonuc = hesapla_sirket_skoru(s)
        if sonuc["score"] < threshold:
            sirketler.append({
                "sirket": s,
                "score": sonuc["score"],
            })

    context = {
        "sirketler": sirketler,
        "threshold": threshold,
    }

    return render(request, "sirket_riskli_list.html", context)


@require_POST
def obligation_complete(request, pk):
    """
    HTML form üzerinden: yükümlülüğü tamamla (is_compliant=True)
    """
    obligation = get_object_or_404(SirketObligation, pk=pk)
    obligation.is_compliant = True
    obligation.save()

    # ilgili şirket dashboard sayfasına dön
    sirket_id = obligation.sirket_id
    return redirect(f"/api/companies/{sirket_id}/dashboard-page/")


@require_POST
def obligation_reset(request, pk):
    """
    HTML form üzerinden: yükümlülüğü geri al (is_compliant=False)
    """
    obligation = get_object_or_404(SirketObligation, pk=pk)
    obligation.is_compliant = False
    obligation.save()

    sirket_id = obligation.sirket_id
    return redirect(f"/api/companies/{sirket_id}/dashboard-page/")


def companies_spa_list(request):
    """
    Server-side SPA list page.
    React yerine template ile liste basıyorsun (companies_spa_list.html).
    """
    sirketler = Sirket.objects.all().order_by("id")
    return render(request, "companies_spa_list.html", {"sirketler": sirketler})


def companies_spa_detail(request, pk):
    """
    SPA detail template:
    React bu sayfada çalışıyor, template sadece id/name'i JS'e vermek için.
    """
    sirket = get_object_or_404(Sirket, pk=pk)
    return render(request, "companies_spa_detail.html", {
        "company_id": sirket.pk,
        "company_name": sirket.name,
    })


@require_http_methods(["GET"])
def sirket_dashboard_api(request, pk):
    """
    GET dashboard JSON (SPA’nın çağırdığı endpoint olarak da kullanılabilir).
    """
    sirket = get_object_or_404(Sirket, pk=pk)
    payload = build_dashboard_payload(sirket)
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


@require_http_methods(["GET"])
def companies_spa_list_api(request):
    qs = Sirket.objects.all().order_by("id")

    # hesaplanan skoru da gömelim (uyum_skoru)
    data = []
    for s in qs:
        sonuc = hesapla_sirket_skoru(s)
        data.append({
            "id": s.id,
            "name": s.name,
            "sector": s.sector,
            "uyum_skoru": sonuc["score"],
        })

    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})
