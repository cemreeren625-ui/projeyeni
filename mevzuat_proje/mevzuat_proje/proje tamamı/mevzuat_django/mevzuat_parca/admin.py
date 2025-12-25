# Django admin panelini özelleştirmek için
from django.contrib import admin

# Admin panelde göstereceğimiz modeller
from .models import Sirket, Duzenleme, SirketObligation


# Sirket modelini admin paneline kaydet + ayarlarını özelleştir
@admin.register(Sirket)
class SirketAdmin(admin.ModelAdmin):
    # Liste ekranında (admin list view) hangi kolonlar görünsün
    list_display = (
        "name",          # şirket adı
        "sector",        # sektör
        "employee_count",# çalışan sayısı
        "location_city", # şehir
        "is_exporter",   # ihracatçı mı
        "created_at",    # oluşturulma zamanı
    )

    # Sağ taraftaki filtre panelinde hangi filtreler olsun
    list_filter = (
        "sector",        # sektöre göre filtre
        "is_exporter",   # ihracatçı mı filtre
        "location_city", # şehir filtre
    )

    # Üstteki arama kutusu hangi alanlarda arama yapsın
    search_fields = ("name",)  # name içinde arar


# Duzenleme modelini admin paneline kaydet + ayarlarını özelleştir
@admin.register(Duzenleme)
class DuzenlemeAdmin(admin.ModelAdmin):
    # Liste ekranında gösterilecek kolonlar
    list_display = (
        "title",        # mevzuat başlığı
        "source",       # kaynak
        "publish_date", # yayın tarihi
        "impact_type",  # etki tipi (zorunlu/risk/teşvik)
        "created_at",   # eklenme zamanı
    )

    # Filtre paneli
    list_filter = (
        "source",       # kaynağa göre filtre
        "impact_type",  # etki tipine göre filtre
        "publish_date", # yayın tarihine göre filtre
    )

    # Arama kutusu: title ve raw_text içinde arama yapar
    search_fields = ("title", "raw_text")


# SirketObligation modelini admin paneline kaydet + ayarlarını özelleştir
@admin.register(SirketObligation)
class SirketObligationAdmin(admin.ModelAdmin):
    # Liste ekranında gösterilecek kolonlar
    list_display = (
        "sirket",        # hangi şirket
        "duzenleme",     # hangi mevzuat
        "is_applicable", # bu şirkete uygulanabilir mi
        "is_compliant",  # tamamlandı mı (uyumlu mu)
        "due_date",      # son tarih
        "risk_level",    # risk seviyesi
        "created_at",    # oluşturulma zamanı
    )

    # Filtre paneli (uygun mu / tamam mı / risk / son tarih)
    list_filter = (
        "is_applicable",
        "is_compliant",
        "risk_level",
        "due_date",
    )

    # Arama kutusu:
    # - sirket__name: şirket adında arama (ForeignKey üzerinden)
    # - duzenleme__title: mevzuat başlığında arama
    search_fields = ("sirket__name", "duzenleme__title")
