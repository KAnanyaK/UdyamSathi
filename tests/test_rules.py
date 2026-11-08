from backend.rules import eligible_products, quote, validate, recommend_bundle

def profile(**overrides):
    p={"business_type":"Retail","employees":2,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"N","gstin":""};p.update(overrides);return p

def test_no_gstin_hides_every_restricted_id():
    ids={p['product_id'] for p in eligible_products(profile())}
    assert not (ids & {"P05","P06","P10","P12","P13","P14","P15","P21","P24"})

def test_city_tier_filter():
    ids={p['product_id'] for p in eligible_products(profile(city_tier=3))}
    assert ids==set()

def test_employee_and_site_minimums():
    ids={p['product_id'] for p in eligible_products(profile(employees=4,sites=2))}
    assert "P03" not in ids and "P05" not in ids and "P10" not in ids and "P21" not in ids
    ids={p['product_id'] for p in eligible_products(profile(employees=10,sites=3,has_gstin="Y",gstin="32TTNXB7384T1ZW"))}
    assert "P10" not in ids  # dependent add-ons require a base link in the candidate bundle
    assert validate(["P01","P10"],profile(employees=10,sites=3,has_gstin="Y",gstin="32TTNXB7384T1ZW"))["valid"]

def test_gstin_required_products_only_for_active_owner():
    without={p['product_id'] for p in eligible_products(profile(employees=30))}
    with_gst={p['product_id'] for p in eligible_products(profile(employees=30,has_gstin="Y",gstin="32TTNXB7384T1ZW"))}
    assert "P06" not in without and "P06" in with_gst
    assert "P05" not in without and "P05" in with_gst

def test_dependency_validation_failover_requires_main_link():
    assert not validate(["P09"])["valid"]
    assert validate(["P01","P09"])["valid"]
    assert not validate(["P10"])["valid"]

def test_price_range_setup_contract_and_install_aggregation():
    q=quote(["P01","P09"])
    assert (q["monthly_min"],q["monthly_max"],q["expected_monthly"])==(1498,1798,1648)
    assert q["setup_total"]==1500
    assert q["contract_months"]==12 and q["install_days"]==5

def test_per_site_quantity_and_longest_contract():
    q=quote(["P02","P10"],profile={"sites":3,"employees":12,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW","city_tier":2})
    assert q["items"][0]["quantity"]==3 and q["items"][1]["quantity"]==3
    assert q["monthly_min"]==11997 and q["monthly_max"]==15897
    assert q["setup_total"]==5000 and q["contract_months"]==24 and q["install_days"]==14

def test_invalid_bundle_never_gets_a_quote():
    q=quote(["P09"])
    assert not q["valid"] and q["monthly_min"]==0

def test_recommendation_is_catalogue_valid_and_tier_aware():
    a=recommend_bundle(profile());assert validate(a["products"])["valid"]
    tier3=recommend_bundle(profile(city_tier=3));assert tier3["products"]==[]
