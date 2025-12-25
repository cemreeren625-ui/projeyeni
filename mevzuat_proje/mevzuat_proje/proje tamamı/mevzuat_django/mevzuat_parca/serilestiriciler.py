from rest_framework import serializers
from .models import Sirket, Duzenleme  # Modelleri import ediyoruz (veritabanı tabloları)

# =========================
# 1) SirketSerializer
# =========================
class SirketSerializer(serializers.ModelSerializer):
    # Modelde olmayan ama API çıktısına eklemek istediğin "hesaplanmış" alan.
    # SerializerMethodField → değeri get_<alan_adı>() fonksiyonundan alır.
    compliance_score = serializers.SerializerMethodField()

    class Meta:
        # Bu serializer hangi modele bağlı? → Sirket
        model = Sirket

        # API'da hangi alanlar görünsün?
        # Buraya yazdıkların JSON çıktısına aynen basılır.
        fields = [
            "id",             # Sirket primary key
            "name",           # Şirket adı
            "sector",         # Sektör (choices)
            "employee_count", # Çalışan sayısı
            "location_city",  # Şehir
            "is_exporter",    # ihracatçı mı? (True/False)
            "created_at",     # kayıt tarihi
            "compliance_score", # hesaplanan uyum skoru (modelde yok)
        ]

    def get_compliance_score(self, obj):
        # compliance_score alanının değerini üretir.
        # obj → şu an serialize edilen Sirket kaydı.

        # Skor hesaplayan fonksiyon views.py içinde durduğu için burada içerden import ediyoruz.
        # (Not: Bu import döngüsel import riskini azaltmak için fonksiyon içinde yapılmış.)
        from .views import hesapla_sirket_skoru

        # Şirketin skorunu hesaplatıyoruz
        result = hesapla_sirket_skoru(obj)

        # result dict'i içinde "score" anahtarı var → onu döndürüyoruz
        return result["score"]


# =========================
# 2) DuzenlemeSerializer
# =========================
class DuzenlemeSerializer(serializers.ModelSerializer):
    class Meta:
        # Bu serializer hangi modele bağlı? → Duzenleme
        model = Duzenleme

        # "__all__" demek: modeldeki tüm alanları API çıktısına bas.
        fields = "__all__"
