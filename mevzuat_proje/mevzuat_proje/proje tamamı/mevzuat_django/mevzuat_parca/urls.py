# Django URL yönlendirme aracı (path ile route tanımlıyoruz)
from django.urls import path

# Aynı app içindeki views.py dosyasını import ediyoruz (endpoint fonksiyonları/sınıfları burada)
from . import views

# Bu liste: gelen URL -> hangi view çalışacak eşlemesi
urlpatterns = [

    # =========================
    # 1) SPA SAYFALARI (HTML)
    # =========================

    # Şirketleri listeleyen SPA giriş sayfası (template render eder)
    # URL: /api/companies-spa/
    path("api/companies-spa/", views.companies_spa_list, name="companies_spa_list"),

    # Tek bir şirketin SPA detay sayfası (React burada çalışıyor, template sadece id/name verir)
    # URL: /api/companies-spa/<id>/
    path("api/companies-spa/<int:pk>/", views.companies_spa_detail, name="companies_spa_detail"),


    # =========================
    # 2) SPA Dashboard JSON (React fetch burada)
    # =========================

    # React’ın detay sayfasında çektiği dashboard JSON endpoint’i
    # URL: /api/companies-spa/<id>/dashboard/
    path(
        "api/companies-spa/<int:pk>/dashboard/",
        views.sirket_dashboard_api,
        name="sirket-dashboard-api"
    ),


    # =========================
    # 3) Obligation toggle (PATCH)
    # =========================

    # React’ta "Tamamlandı" / "Geri al" butonlarının PATCH attığı endpoint
    # Body: {"is_compliant": true/false}
    # URL: /api/obligations/<obligation_id>/status/
    path(
        "api/obligations/<int:pk>/status/",
        views.obligation_status_api,
        name="obligation-status-api"
    ),


    # =========================
    # 4) DRF JSON API'ler (CRUD)
    # =========================

    # Şirket listele (GET) / şirket oluştur (POST)
    # URL: /api/companies/
    path("api/companies/", views.SirketListCreateView.as_view(), name="Sirket-list-create"),

    # Şirket detay (GET) / güncelle (PUT/PATCH) / sil (DELETE)
    # URL: /api/companies/<id>/
    path("api/companies/<int:pk>/", views.SirketDetailView.as_view(), name="Sirket-detail"),

    # Düzenleme listele (GET) / düzenleme oluştur (POST)
    # URL: /api/Duzenlemes/
    path("api/Duzenlemes/", views.DuzenlemeListCreateView.as_view(), name="Duzenleme-list-create"),

    # Düzenleme detay (GET) / güncelle (PUT/PATCH) / sil (DELETE)
    # URL: /api/Duzenlemes/<id>/
    path("api/Duzenlemes/<int:pk>/", views.DuzenlemeDetailView.as_view(), name="Duzenleme-detail"),


    # =========================
    # 5) Eski dashboard JSON (klasik endpoint)
    # =========================

    # Eski JSON dashboard endpoint’i (SPA olmayan yerler kullanabilir)
    # URL: /api/companies/<id>/dashboard/
    path("api/companies/<int:pk>/dashboard/", views.Sirket_dashboard, name="Sirket-dashboard"),


    # =========================
    # 6) HTML form aksiyonları (POST)
    # =========================

    # HTML panelde "Tamamlandı" butonu (form POST)
    # URL: /api/obligations/<id>/complete/
    path("api/obligations/<int:pk>/complete/", views.obligation_complete, name="obligation-complete"),

    # HTML panelde "Geri al" butonu (form POST)
    # URL: /api/obligations/<id>/reset/
    path("api/obligations/<int:pk>/reset/", views.obligation_reset, name="obligation-reset"),


    # =========================
    # 7) HTML sayfalar (eski panel ekranları)
    # =========================

    # Şirketleri HTML liste halinde gösteren sayfa
    # URL: /api/companies-dashboard/
    path("api/companies-dashboard/", views.sirket_list_page, name="sirket-list-page"),

    # Riskli şirketleri HTML liste halinde gösteren sayfa
    # URL: /api/companies-risky/
    path("api/companies-risky/", views.sirket_riskli_list_page, name="sirket-riskli-list-page"),

    # Klasik Django HTML dashboard sayfası
    # URL: /api/companies/<id>/dashboard-page/
    path("api/companies/<int:pk>/dashboard-page/", views.sirket_dashboard_page, name="sirket-dashboard-page"),
    
    # SPA (React) için ŞİRKET LİSTESİ JSON endpoint’i:
    # /api/companies-spa-list/ -> JSON döner (React bunu çeker)
    # NOT: /api/companies-spa/ HTML sayfadır (template render), JSON değildir.
    path("api/companies-spa-list/", views.companies_spa_list_api, name="companies-spa-list-api"),
]
