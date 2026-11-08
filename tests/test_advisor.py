from backend.advisor import respond

def test_eight_scripted_scenarios():
    cases=[
        ("Kirana shop with GSTIN",{"business_type":"Retail","employees":4,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW"},{"P01"}),
        ("salon without GSTIN",{"business_type":"Services","employees":3,"sites":1,"city":"Jaipur","city_tier":2,"has_gstin":"N"},{"P01"}),
        ("three site restaurant",{"business_type":"Restaurant","employees":35,"sites":3,"city":"Mumbai","city_tier":1,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW"},{"P02"}),
        ("manufacturer",{"business_type":"Manufacturing","employees":25,"sites":1,"city":"Pune","city_tier":1,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW"},{"P03"}),
        ("tier 3",{"business_type":"Retail","employees":4,"sites":1,"city":"Small town","city_tier":3,"has_gstin":"N"},set()),
        ("mobile only",{"business_type":"Retail","employees":2,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"N","mobile_only":True},{"P07"}),
        ("GSTIN lane",{"business_type":"Professional offices","employees":12,"sites":1,"city":"Kochi","city_tier":2,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW"},{"P02"}),
        ("no GSTIN safeguards",{"business_type":"Professional offices","employees":25,"sites":2,"city":"Delhi","city_tier":1,"has_gstin":"N"},{"P01"}),
    ]
    for text,p,required in cases:
        result=respond(text,p)
        assert result["quote"]["valid"],text
        assert required.issubset(set(result["bundle"]["products"])),(text,result["bundle"])
        if p["has_gstin"]=="N":assert not(set(result["bundle"]["products"])&{"P05","P06","P10","P12","P13","P14","P15","P21","P24"})
        assert result["questions_used"]<=5

def test_hindi_detection():
    assert respond("मुझे दुकान के लिए इंटरनेट चाहिए",{"has_gstin":"N"})["language"]=="hi"
