# mevzuat_parca/nlp_rules.py

def analyze_regulation_text(text: str):
    """
    Çok basit bir kural tabanlı analiz:
    - tags: ["vergi", "KDV", "SGK", "ihracat", "KVKK", ...]
    - sectors: ["yazilim", "imalat", "perakende", "lojistik"]
    - impact_type: "zorunlu" / "opsiyonel_tesvik" / "risk"
    """

    # Eğer text None/"" gibi boş gelirse analiz yapamayız.
    # Bu yüzden boş listeler ve None döndürüp çıkıyoruz.
    if not text:
        return [], [], None

    # Metni küçük harfe çeviriyoruz ki arama yaparken büyük/küçük harf farkı sorun olmasın.
    t = text.lower()

    # tags ve sectors tekrar eden değerleri engellemek için set olarak tutuluyor.
    tags = set()
    sectors = set()

    # impact_type tek bir değer olacak (zorunlu / teşvik / risk).
    impact_type = None

    # -------------------------
    # TAGLER (etiketler)
    # -------------------------
    # "kdv" veya "katma değer vergisi" geçiyorsa hem genel "vergi" hem de "KDV" tag’ini ekliyoruz.
    if "kdv" in t or "katma değer vergisi" in t:
        tags.update(["vergi", "KDV"])

    # "gelir vergisi" geçiyorsa vergi + gelir_vergisi etiketlerini ekler.
    if "gelir vergisi" in t:
        tags.update(["vergi", "gelir_vergisi"])

    # "kurumlar vergisi" geçiyorsa vergi + kurumlar_vergisi ekler.
    if "kurumlar vergisi" in t:
        tags.update(["vergi", "kurumlar_vergisi"])

    # "sgk" veya "sosyal güvenlik" geçiyorsa SGK tag’i eklenir.
    if "sgk" in t or "sosyal güvenlik" in t:
        tags.add("SGK")

    # "ihracat" veya "ihracatçı" geçiyorsa ihracat tag’i eklenir.
    if "ihracat" in t or "ihracatçı" in t:
        tags.add("ihracat")

    # "kosgeb" geçiyorsa KOSGEB tag’i eklenir.
    if "kosgeb" in t:
        tags.add("KOSGEB")

    # "kvkk" veya "kişisel veri" geçiyorsa KVKK ve kişisel_veri tag’leri eklenir.
    if "kvkk" in t or "kişisel veri" in t:
        tags.update(["KVKK", "kişisel_veri"])

    # -------------------------
    # SEKTÖRLER
    # -------------------------
    # any(...) → listede saydığımız kelimelerden herhangi biri metinde geçiyor mu diye bakar.
    # Geçiyorsa ilgili sektörü ekler.

    # Yazılım sektörü: yazılım/bilişim/bt/saas gibi kelimelerden biri geçerse "yazilim" eklenir.
    if any(w in t for w in ["yazılım", "bilişim", "bt", "saas"]):
        sectors.add("yazilim")

    # İmalat sektörü: imalat/üretim/fabrika geçerse "imalat" eklenir.
    if any(w in t for w in ["imalat", "üretim", "fabrika"]):
        sectors.add("imalat")

    # Perakende sektörü: perakende/mağaza/market/satış noktası geçerse "perakende" eklenir.
    if any(w in t for w in ["perakende", "mağaza", "market", "satış noktası"]):
        sectors.add("perakende")

    # Lojistik sektörü: lojistik/taşımacılık/kargo/nakliye geçerse "lojistik" eklenir.
    if any(w in t for w in ["lojistik", "taşımacılık", "kargo", "nakliye"]):
        sectors.add("lojistik")

    # -------------------------
    # ETKİ TİPİ (impact_type)
    # -------------------------
    # Burada sırayla kontrol ediyoruz:
    # 1) zorunlu mu?
    # 2) teşvik mi?
    # 3) risk/ceza mı?
    #
    # Not: Burada if/elif zinciri olduğu için
    # ilk yakalanan kategori impact_type olur.

    # Zorunlu ifadelerden biri geçerse impact_type = "zorunlu"
    if any(w in t for w in ["zorunludur", "yapmak zorundadır", "yükümlüdür", "uygulamak zorundadır"]):
        impact_type = "zorunlu"

    # Zorunlu değilse ama teşvik/hibe/destek kelimeleri geçiyorsa "opsiyonel_tesvik"
    elif any(w in t for w in ["teşvik", "hibe", "destek programı", "yardım programı"]):
        impact_type = "opsiyonel_tesvik"

    # Zorunlu veya teşvik değilse ama ceza/risk/yaptırım kelimeleri geçiyorsa "risk"
    elif any(w in t for w in ["ceza", "idari para cezası", "risk", "yaptırım"]):
        impact_type = "risk"

    # set'leri list'e çevirip döndürüyoruz (JSONField için uygun format).
    return list(tags), list(sectors), impact_type
