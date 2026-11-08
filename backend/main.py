from __future__ import annotations
import csv, json, os, sqlite3, uuid, re, shutil, subprocess, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from difflib import SequenceMatcher
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine
from .rules import eligible_products, recommend_bundle, quote, validate
from .advisor import respond
from .partner_model import get_model, predict

ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv("DB_PATH","/tmp/udyamsathi.db" if os.getenv("VERCEL") else ROOT/"data"/"udyamsathi.db"))
class OrderRecord(SQLModel,table=True):
    __tablename__="orders"
    id:str=Field(primary_key=True);created_at:str;state:str;profile:str;bundle:str;quote:str;expected_by:str;install_slot:str
class ConsentRecord(SQLModel,table=True):
    __tablename__="consent_ledger"
    id:int|None=Field(default=None,primary_key=True);order_id:str;ts:str;purpose:str;decision:bool;notice_version:str
class KycRecord(SQLModel,table=True):
    __tablename__="kyc_fields"
    id:int|None=Field(default=None,primary_key=True);order_id:str;doc_type:str;fields:str;validation:str
class OrderEvent(SQLModel,table=True):
    __tablename__="order_events"
    id:int|None=Field(default=None,primary_key=True);order_id:str;state:str;ts:str
engine=create_engine(f"sqlite:///{DB.as_posix()}",connect_args={"check_same_thread":False})
app=FastAPI(title="Udyam Sathi",version="0.1.0",description="Synthetic telecom onboarding prototype")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
def rows(file):
    with (ROOT/"data"/file).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def db():
    SQLModel.metadata.create_all(engine)
    conn=sqlite3.connect(DB);conn.row_factory=sqlite3.Row
    columns={r[1] for r in conn.execute("PRAGMA table_info(orders)")}
    if columns and "install_slot" not in columns:conn.execute("ALTER TABLE orders ADD COLUMN install_slot TEXT NOT NULL DEFAULT ''")
    return conn
class ProfileRequest(BaseModel): profile:dict
class QuoteRequest(BaseModel): bundle:list[str];toggles:dict[str,bool]={};profile:dict={}
class OrderRequest(BaseModel): profile:dict;bundle:list[str];quote:dict;consents:dict[str,bool]={}
class ConsentRequest(BaseModel): purpose:str;decision:bool
class StepRequest(BaseModel): pass
class MessageRequest(BaseModel): message:str;profile:dict={}

@app.get("/api/health")
def health(): return {"ok":True,"service":"Udyam Sathi","synthetic_data":True}
@app.post("/api/advisor")
def advisor(req:MessageRequest): return respond(req.message,req.profile)
@app.post("/api/products/eligible")
def products(req:ProfileRequest): return {"products":eligible_products(req.profile)}
@app.post("/api/quote")
def build_quote(req:QuoteRequest): return quote(req.bundle,req.toggles,req.profile)
@app.post("/api/recommend")
def recommend(req:ProfileRequest):
    b=recommend_bundle(req.profile);return {"bundle":b,"quote":quote(b,profile=req.profile)}
@app.get("/api/gstin/{identifier}")
def gstin(identifier:str):
    record=next((r for r in rows("mock_gstin_registry.csv") if r["gstin"].upper()==identifier.upper()),None)
    if not record: raise HTTPException(404,"GSTIN not found in synthetic registry")
    return record
@app.get("/api/udyam/{identifier}")
def udyam(identifier:str):
    record=next((r for r in rows("mock_udyam_registry.csv") if r["udyam_number"].upper()==identifier.upper()),None)
    if not record: raise HTTPException(404,"Udyam number not found in synthetic registry")
    return record
@app.post("/api/orders")
def create_order(req:OrderRequest):
    check=validate(req.bundle,req.profile)
    if not check["valid"]: raise HTTPException(400,check["errors"])
    oid="US-"+uuid.uuid4().hex[:8].upper();now=datetime.now(timezone.utc);expected=now+timedelta(days=int(req.quote.get("install_days",7)))
    conn=db();conn.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)",(oid,now.isoformat(),"Quote accepted",json.dumps(req.profile),json.dumps(req.bundle),json.dumps(req.quote),expected.isoformat(),expected.isoformat()))
    conn.execute("INSERT INTO order_events(order_id,state,ts) VALUES(?,?,?)",(oid,"Quote accepted",now.isoformat()))
    for purpose,decision in req.consents.items():conn.execute("INSERT INTO consent_ledger(order_id,ts,purpose,decision,notice_version) VALUES(?,?,?,?,?)",(oid,now.isoformat(),purpose,int(bool(decision)),"v1.0"))
    conn.commit();conn.close();return {"order_id":oid,"state":"Quote accepted","created_at":now.isoformat(),"expected_by":expected.isoformat(),"install_slot":expected.isoformat()}
@app.get("/api/orders/{order_id}")
def get_order(order_id:str):
    conn=db();row=conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone();conn.close()
    if not row:raise HTTPException(404,"Order not found")
    result=dict(row);result["profile"]=json.loads(result["profile"]);result["bundle"]=json.loads(result["bundle"]);result["quote"]=json.loads(result["quote"]);conn=db();result["events"]=[dict(x) for x in conn.execute("SELECT state,ts FROM order_events WHERE order_id=? ORDER BY id",(order_id,))];conn.close();return result
@app.post("/api/orders/{order_id}/next")
def next_step(order_id:str):
    states=["Quote accepted","KYC pending","KYC verified","Install scheduled","Installed","Activated"]
    conn=db();row=conn.execute("SELECT state FROM orders WHERE id=?",(order_id,)).fetchone()
    if not row:conn.close();raise HTTPException(404,"Order not found")
    state=states[min(states.index(row["state"])+1,len(states)-1)];now=datetime.now(timezone.utc).isoformat();conn.execute("UPDATE orders SET state=? WHERE id=?",(state,order_id));conn.execute("INSERT INTO order_events(order_id,state,ts) VALUES(?,?,?)",(order_id,state,now));conn.commit();conn.close();return {"state":state,"timestamp":now}
@app.get("/api/consent/{order_id}")
def consent_history(order_id:str):
    conn=db();items=[dict(x) for x in conn.execute("SELECT ts,purpose,decision,notice_version FROM consent_ledger WHERE order_id=? ORDER BY id",(order_id,))];conn.close();return items
@app.post("/api/consent/{order_id}")
def record_consent(order_id:str,req:ConsentRequest):
    allowed={"identity_check","address_check","install_scheduling","whatsapp_updates"}
    if req.purpose not in allowed:raise HTTPException(400,"Unknown consent purpose")
    conn=db();order=conn.execute("SELECT id FROM orders WHERE id=?",(order_id,)).fetchone()
    if not order:conn.close();raise HTTPException(404,"Order not found")
    conn.execute("INSERT INTO consent_ledger(order_id,ts,purpose,decision,notice_version) VALUES(?,?,?,?,?)",(order_id,datetime.now(timezone.utc).isoformat(),req.purpose,int(req.decision),"v1.0"));conn.commit();conn.close();return {"recorded":True,"purpose":req.purpose,"decision":req.decision}
def similarity(a,b):return SequenceMatcher(None," ".join(str(a).lower().split())," ".join(str(b).lower().split())).ratio()
@app.post("/api/kyc/validate")
async def validate_document(request:Request,doc_type:str="other",order_id:str="demo",filename:str="upload.bin"):
    # Temporary file is deleted in all cases; only extracted fields and validation results are retained.
    purpose="address_check" if doc_type=="address_proof" else "identity_check"
    conn=db();decision=conn.execute("SELECT decision FROM consent_ledger WHERE order_id=? AND purpose=? ORDER BY id DESC LIMIT 1",(order_id,purpose)).fetchone();conn.close()
    if not decision or not decision["decision"]:raise HTTPException(403,f"Consent for {purpose} is required before upload")
    content=await request.body()
    extracted="";ocr_available=bool(shutil.which("tesseract"))
    temp_path=None
    try:
        if ocr_available:
            with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".png",delete=False) as temp:
                temp.write(content);temp_path=temp.name
            result_ocr=subprocess.run(["tesseract",temp_path,"stdout"],capture_output=True,text=True,timeout=30)
            extracted=result_ocr.stdout or ""
    except Exception:
        ocr_available=False
    finally:
        if temp_path and os.path.exists(temp_path):os.remove(temp_path)
    synthetic=bool(re.search(r"SPECIMEN|NOT\s+A\s+VALID\s+DOCUMENT",extracted,re.I)) or bool(re.match(r"K\d{2}_",filename))
    gst_match=re.search(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b",extracted,re.I)
    udyam_match=re.search(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}",extracted,re.I)
    name_match=re.search(r"(?:Legal name|Enterprise name|Billed to)\s*\n?\s*:?\s*([^\n]+)",extracted,re.I)
    addr_match=re.search(r"(?:Address of principal|Supply address)\s*\n?\s*:?\s*([^\n]+)",extracted,re.I)
    fields={"document_name":filename,"document_type":doc_type,"extracted_name":name_match.group(1).strip() if name_match else None,"extracted_address":addr_match.group(1).strip() if addr_match else None,"gstin":gst_match.group(0).upper() if gst_match else None,"udyam_number":udyam_match.group(0).upper() if udyam_match else None,"synthetic_specimen":synthetic,"ocr_status":"complete" if ocr_available else "OCR engine unavailable; review required"}
    checks=[{"name":"synthetic_document","passed":not synthetic,"detail":"Specimen watermark detected" if synthetic else "No specimen watermark found"}]
    conf={"document_type":0.99,"synthetic_specimen":0.99 if synthetic else (0.82 if ocr_available else 0.0)}
    if fields["gstin"]:
        registry=next((x for x in rows("mock_gstin_registry.csv") if x["gstin"].upper()==fields["gstin"]),None)
        checks.append({"name":"gstin_registry","passed":bool(registry and registry["status"].lower()=="active"),"detail":registry["status"] if registry else "GSTIN not found"});conf["gstin"]=0.95
    if fields["udyam_number"]:
        registry=next((x for x in rows("mock_udyam_registry.csv") if x["udyam_number"].upper()==fields["udyam_number"]),None)
        checks.append({"name":"udyam_registry","passed":bool(registry),"detail":"Udyam record found" if registry else "Udyam number not found"});conf["udyam_number"]=0.95
    if fields["extracted_name"]:conf["extracted_name"]=0.80
    if fields["extracted_address"]:conf["extracted_address"]=0.75
    if fields["extracted_name"]:
        registry_rows=rows("mock_gstin_registry.csv")
        best=max((max(similarity(fields["extracted_name"],r["legal_name"]),similarity(fields["extracted_name"],r["trade_name"])) for r in registry_rows),default=0)
        checks.append({"name":"business_name_match","passed":best>=0.72,"detail":f"Best registry name similarity {best:.2f}"});conf["business_name_match"]=round(best,2)
    if fields["extracted_address"]:
        registry_rows=rows("mock_gstin_registry.csv")
        best=max((similarity(fields["extracted_address"],r["principal_place_of_business"]) for r in registry_rows),default=0)
        checks.append({"name":"address_match","passed":best>=0.72,"detail":f"Best registry address similarity {best:.2f}"});conf["address_match"]=round(best,2)
    result={"fields":fields,"confidence":conf,"checks":checks,"review_required":any(not c["passed"] for c in checks) or not ocr_available,"ocr_text_for_debug":None}
    conn=db();conn.execute("INSERT INTO kyc_fields(order_id,doc_type,fields,validation) VALUES(?,?,?,?)",(order_id,doc_type,json.dumps(fields),json.dumps(result)));conn.commit();conn.close();del content
    return result
@app.get("/api/kyc/review")
def kyc_exception_review():
    conn=db();items=[]
    for row in conn.execute("SELECT id,order_id,doc_type,fields,validation FROM kyc_fields ORDER BY id DESC"):
        validation=json.loads(row["validation"])
        if not validation.get("review_required"):continue
        fields=json.loads(row["fields"])
        for key in ("gstin","udyam_number"):
            if fields.get(key):fields[key]=fields[key][:3]+"••••••"+fields[key][-2:]
        items.append({"id":row["id"],"order_id":row["order_id"],"doc_type":row["doc_type"],"fields":fields,"validation":validation})
    conn.close();return items
@app.post("/api/whatsapp/webhook")
def whatsapp(req:MessageRequest):return {"channel":"mock-whatsapp","result":respond(req.message,req.profile)}
@app.get("/api/partner/leads")
def partner_leads():
    leads=rows("smb_leads.csv");opened=[];model=get_model();scores=predict(leads,model)
    for r,score in zip(leads,scores):
        if r.get("outcome","").lower()=="dropped" or r.get("stage_reached","").lower() in {"chat dropped","kyc failed","quote abandoned"}:
            spend=float(r.get("monthly_telecom_spend_inr") or 0)
            opened.append({"lead_id":r["lead_id"],"business_name":r["business_name"],"segment":r["segment"],"city":r["city"],"stage":r["stage_reached"],"drop_reason":r["drop_reason"] or "Quote not completed","propensity":round(score,2),"monthly_spend":spend,"products_of_interest":r["products_of_interest"]})
    return sorted(opened,key=lambda x:x["propensity"],reverse=True)[:100]
@app.get("/api/partner/metrics")
def metrics():
    leads=rows("smb_leads.csv");model=get_model();return {"leads":len(leads),"activated":sum(r["outcome"].lower()=="activated" for r in leads),"activation_rate":round(sum(r["outcome"].lower()=="activated" for r in leads)/max(len(leads),1),3),"eligible_for_followup":sum(r["outcome"].lower()=="dropped" for r in leads),"holdout_auc":model["auc"],"top_features":model["features"]}

# Vercel serves the built Vite UI through the same FastAPI function. In local
# development, Vite continues to provide its own hot-reload server.
FRONTEND_DIST=ROOT/"frontend"/"dist"
if FRONTEND_DIST.exists():
    app.mount("/",StaticFiles(directory=FRONTEND_DIST,html=True),name="frontend")
