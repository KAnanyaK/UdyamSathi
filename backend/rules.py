"""Deterministic eligibility and pricing rules. The catalogue is the price source of truth."""
from __future__ import annotations
import os
import csv
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = Path(os.getenv("CATALOGUE_PATH", ROOT / "data" / "product_catalogue.csv"))

def _catalogue() -> list[dict]:
    return pd.read_csv(CATALOGUE_PATH, keep_default_na=False).to_dict(orient="records")

def _n(profile: dict, *keys: str, default=0):
    for key in keys:
        if profile.get(key) not in (None, ""):
            try: return int(float(profile[key]))
            except (TypeError, ValueError): pass
    return default

def _has_gstin(profile: dict) -> bool:
    identifier=str(profile.get("gstin", "")).strip().upper()
    if str(profile.get("has_gstin", "N")).strip().upper() not in {"Y", "YES", "TRUE", "1"} or not identifier:return False
    registry=ROOT/"data"/"mock_gstin_registry.csv"
    if not registry.exists():return False
    with registry.open(encoding="utf-8-sig",newline="") as f:
        return any(r["gstin"].upper()==identifier and r["status"].strip().lower()=="active" for r in csv.DictReader(f))

def _city_tier(profile: dict) -> int:
    return _n(profile, "city_tier", "tier", default=2)

def eligible_products(profile: dict) -> list[dict]:
    products = _catalogue()
    result = []
    for product in products:
        tiers = {int(x) for x in str(product["available_city_tiers"]).split(";") if x.strip()}
        if _city_tier(profile) not in tiers: continue
        if _n(profile, "employees", "employee_count", default=1) < int(product["min_employees"]): continue
        if _n(profile, "sites", "num_sites", default=1) < int(product["min_sites"]): continue
        if str(product["requires_gstin"]).upper() == "Y" and not _has_gstin(profile): continue
        # A dependency indicates an add-on that cannot be independently recommended.
        if product["requires_one_of"]: continue
        result.append(product)
    return result

def validate(bundle: list[str] | dict, profile: dict | None = None) -> dict:
    ids = bundle.get("products", []) if isinstance(bundle, dict) else bundle
    ids = list(dict.fromkeys(ids))
    catalog = {p["product_id"]: p for p in _catalogue()}
    errors = [f"Unknown product {pid}" for pid in ids if pid not in catalog]
    selected = {pid for pid in ids if pid in catalog}
    for pid in list(selected):
        p = catalog[pid]
        if p["requires_one_of"] and not (set(str(p["requires_one_of"]).split("|")) & selected):
            errors.append(f"{pid} requires one of {p['requires_one_of']}")
        if profile is not None:
            tiers={int(x) for x in str(p["available_city_tiers"]).split(";") if x.strip()}
            if _city_tier(profile) not in tiers or _n(profile,"employees","employee_count",default=1)<int(p["min_employees"]) or _n(profile,"sites","num_sites",default=1)<int(p["min_sites"]):errors.append(f"{pid} is not eligible for this profile")
            if str(p["requires_gstin"]).upper()=="Y" and not _has_gstin(profile):errors.append(f"{pid} requires an active GSTIN")
    return {"valid": not errors, "errors": errors, "products": ids}

def recommend_bundle(profile: dict) -> dict:
    eligible = eligible_products(profile)
    ids = {p["product_id"] for p in eligible}
    category = str(profile.get("business_type", profile.get("segment", ""))).lower()
    mobile_only = bool(profile.get("mobile_only"))
    if profile.get("price_objection"):
        if mobile_only: chosen=["P07"] if "P07" in ids else []
        else:
            cheaper=[p for p in eligible if p["category"]=="Connectivity" and p["unit"]=="per site"]
            cheapest=min(cheaper,key=lambda p:int(p["price_min_inr_per_month"])) if cheaper else None
            chosen=[cheapest["product_id"]] if cheapest else []
        return {"products":chosen,"reason":"A lower-cost eligible connection option."}
    if mobile_only:
        chosen = ["P07"] if "P07" in ids else []
    else:
        main = "P01" if _city_tier(profile) in (1, 2) else "P02"
        chosen = [main] if main in ids else []
        # Match catalogue segments and make a modest, useful starter set.
        candidates = [p for p in eligible if str(p["target_segments"]).lower().find("micro") >= 0]
        if any(x in category for x in ("manufact", "factory")):
            candidates = [p for p in eligible if "mfg" in str(p["target_segments"]).lower()]
        elif any(x in category for x in ("office", "clinic", "professional", "legal")):
            candidates = [p for p in eligible if "prof" in str(p["target_segments"]).lower()]
        elif _n(profile, "sites", "num_sites", default=1) > 1:
            candidates = [p for p in eligible if "multi" in str(p["target_segments"]).lower() or "micro" in str(p["target_segments"]).lower()]
        else:
            candidates = [p for p in eligible if "micro" in str(p["target_segments"]).lower()]
        for p in candidates:
            pid = p["product_id"]
            if pid not in chosen and len(chosen) < 3: chosen.append(pid)
        # Ensure a valid core link is present for dependent failover add-ons.
        chosen = [x for x in chosen if x != "P09"]
    return {"products": chosen, "reason": "A practical starter bundle based on your business size, city and needs."}

def quote(bundle: list[str] | dict, toggles: dict | None = None, profile: dict | None = None) -> dict:
    toggles = toggles or {}
    ids = list(bundle.get("products", [])) if isinstance(bundle, dict) else list(bundle)
    for pid, enabled in toggles.items():
        if enabled and pid not in ids: ids.append(pid)
        if not enabled: ids = [x for x in ids if x != pid]
    check = validate(ids, profile)
    if not check["valid"]: return {**check, "items": [], "monthly_min": 0, "monthly_max": 0, "expected_monthly": 0, "setup_total": 0, "contract_months": 0, "install_days": 0}
    catalog = {p["product_id"]: p for p in _catalogue()}
    items = []
    for pid in ids:
        p = catalog[pid]
        quantity = _n(profile or {}, "sites", "num_sites", default=1) if p["unit"] == "per site" else 1
        low, high = int(p["price_min_inr_per_month"]) * quantity, int(p["price_max_inr_per_month"]) * quantity
        items.append({"product_id":pid, "name":p["product_name"], "description":p["description"], "quantity":quantity, "unit":p["unit"], "monthly_min":low, "monthly_max":high, "setup_fee":int(p["one_time_setup_inr"]), "contract_months":int(p["min_contract_months"]), "install_days":int(p["typical_install_days"])})
    low, high = sum(x["monthly_min"] for x in items), sum(x["monthly_max"] for x in items)
    return {"valid":True,"errors":[],"products":ids,"items":items,"monthly_min":low,"monthly_max":high,"expected_monthly":round((low+high)/2),"setup_total":sum(x["setup_fee"] for x in items),"contract_months":max([x["contract_months"] for x in items], default=0),"install_days":max([x["install_days"] for x in items],default=0)}
