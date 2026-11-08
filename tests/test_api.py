from fastapi.testclient import TestClient
from sqlmodel import create_engine
from backend import main
from backend.rules import quote

def client_for(tmp_path,monkeypatch):
    path=tmp_path/"api-test.db"
    monkeypatch.setattr(main,"DB",path)
    monkeypatch.setattr(main,"engine",create_engine(f"sqlite:///{path.as_posix()}",connect_args={"check_same_thread":False}))
    return TestClient(main.app)

def test_api_quote_registry_and_inactive_lane(tmp_path,monkeypatch):
    client=client_for(tmp_path,monkeypatch)
    assert client.get("/api/health").json()["ok"]
    assert client.get("/api/gstin/32TTNXB7384T1ZW").json()["status"]=="Active"
    assert client.get("/api/udyam/UDYAM-KL-00-3078801").status_code==200
    profile={"business_type":"Retail","employees":2,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"N"}
    response=client.post("/api/quote",json={"bundle":["P01","P10"],"profile":profile})
    assert response.status_code==200 and not response.json()["valid"]
    active={**profile,"employees":15,"sites":3,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW"}
    result=client.post("/api/quote",json={"bundle":["P02","P10"],"profile":active}).json()
    assert result["valid"] and result["items"][0]["quantity"]==3

def test_order_timestamps_append_only_consent_and_specimen_review(tmp_path,monkeypatch):
    client=client_for(tmp_path,monkeypatch)
    profile={"business_type":"Retail","employees":2,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"N"}
    q=quote(["P01"],profile=profile)
    created=client.post("/api/orders",json={"profile":profile,"bundle":["P01"],"quote":q,"consents":{"identity_check":False,"address_check":False}})
    assert created.status_code==200
    oid=created.json()["order_id"]
    assert client.get(f"/api/orders/{oid}").json()["events"][0]["state"]=="Quote accepted"
    blocked=client.post(f"/api/kyc/validate?doc_type=gst_certificate&order_id={oid}&filename=K01_gst_certificate.png",content=b"synthetic sample")
    assert blocked.status_code==403
    assert client.post(f"/api/consent/{oid}",json={"purpose":"identity_check","decision":True}).status_code==200
    checked=client.post(f"/api/kyc/validate?doc_type=gst_certificate&order_id={oid}&filename=K01_gst_certificate.png",content=b"synthetic sample").json()
    assert checked["fields"]["synthetic_specimen"] and checked["review_required"]
    assert client.get("/api/kyc/review").json()[0]["fields"].get("gstin") in (None, "32T••••••ZW")
    assert len(client.get(f"/api/consent/{oid}").json())==3
    next_state=client.post(f"/api/orders/{oid}/next").json()
    assert next_state["state"]=="KYC pending"
    assert len(client.get(f"/api/orders/{oid}").json()["events"])==2
