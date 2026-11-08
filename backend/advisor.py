"""Bilingual advisor. Gemini is optional; rules and prices always stay deterministic."""
import json, logging, os, re, csv
from pathlib import Path
from functools import lru_cache
from .rules import eligible_products, recommend_bundle, quote, validate

log=logging.getLogger("udyamsathi.advisor")

def _configured_key():
    if os.getenv("GEMINI_API_KEY"):return os.getenv("GEMINI_API_KEY")
    env_file=Path(__file__).resolve().parents[1]/".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):return line.split("=",1)[1].strip().strip("\"'")
    return ""

def _gemini_reply(message,lang,profile,bundle,price):
    key=_configured_key()
    if not key:return None
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=key)
        declarations=[
            {"name":"get_eligible_products","description":"Fetch eligible catalogue product IDs for the current profile; never infer eligibility.","parameters":{"type":"OBJECT","properties":{}}},
            {"name":"build_quote","description":"Get a deterministic quote for a product ID list.","parameters":{"type":"OBJECT","properties":{"products":{"type":"ARRAY","items":{"type":"STRING"}}},"required":["products"]}},
            {"name":"add_addon","description":"Ask the deterministic rules to add one product to the current bundle.","parameters":{"type":"OBJECT","properties":{"product_id":{"type":"STRING"}},"required":["product_id"]}},
            {"name":"remove_addon","description":"Ask the deterministic rules to remove one product from the current bundle.","parameters":{"type":"OBJECT","properties":{"product_id":{"type":"STRING"}},"required":["product_id"]}},
        ]
        config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=declarations)],automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),temperature=0.2)
        log.info("Gemini advisor request; identifiers masked; language=%s; profile fields=%s",lang,sorted(profile.keys()))
        prompt=(f"Answer in {'Hindi' if lang=='hi' else 'English'}. You are a helpful SME telecom guide. "
                "Use function tools for eligibility and quote questions. Never invent eligibility or prices. "
                "Do not write any price, currency amount, identifier, or more than 3 short reasons. "
                "Use only these deterministic recommendations and explain them simply. "
                f"Owner message: {message}\nProfile (synthetic): {json.dumps({k:v for k,v in profile.items() if k not in {'gstin','udyam_number'}},ensure_ascii=False)}\n"
                f"Allowed bundle product IDs: {bundle.get('products',[])}\nExpected price is supplied separately by the verified quote UI.")
        response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),contents=prompt,config=config)
        function_calls=getattr(response,"function_calls",None) or []
        if function_calls:
            parts=[]
            for call in function_calls:
                args=dict(call.args or {});pid=args.get("product_id");prods=eligible_products(profile);allowed={p["product_id"] for p in prods}
                if call.name=="get_eligible_products":result={"products":[{k:p[k] for k in ("product_id","product_name","description")} for p in prods]}
                elif call.name=="build_quote":result=quote(args.get("products",[]),profile=profile)
                elif call.name=="add_addon":
                    candidate=list(bundle.get("products",[]))+([pid] if pid in allowed else [])
                    result=quote(candidate,profile=profile) if pid in allowed else {"valid":False,"errors":["Product is not eligible"]}
                elif call.name=="remove_addon":result=quote([x for x in bundle.get("products",[]) if x!=pid],profile=profile)
                else:result={"error":"Unknown tool"}
                parts.append(types.Part.from_function_response(name=call.name,response=result))
            history=[prompt,response.candidates[0].content,types.Content(role="tool",parts=parts)]
            response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),contents=history,config=types.GenerateContentConfig(temperature=0.2))
        text=(getattr(response,"text",None) or "").strip()
        if not text or re.search(r"₹|\bINR\b|\b\d{3,}\b",text,re.I):return None
        return text
    except Exception as exc:
        log.warning("Gemini advisor fallback (%s)",type(exc).__name__)
        return None

QUESTIONS = ["What kind of business do you run?", "How many people work there?", "How many business locations do you have?", "Which city is the main location in?", "Do you currently have business internet or tools, and do you have GSTIN or Udyam?"]

@lru_cache(maxsize=1)
def _cities():
    path=Path(__file__).resolve().parents[1]/"data"/"smb_leads.csv"
    if not path.exists():return {}
    with path.open(encoding="utf-8-sig",newline="") as f:return {r["city"].lower():(r["city"],int(r["city_tier"])) for r in csv.DictReader(f) if r.get("city") and r.get("city_tier")}
def language_of(text: str, preferred: str = "") -> str:
    if preferred.lower().startswith("hi") or any("\u0900" <= c <= "\u097f" for c in text): return "hi"
    return "en"

def respond(message: str, profile: dict | None = None) -> dict:
    profile = dict(profile or {})
    lang = language_of(message, str(profile.get("preferred_language", "")))
    low = message.lower()
    if any(x in low for x in ("too expensive", "price is high", "cheaper", "महंगा", "महँगा", "कम कीमत")):
        profile["price_objection"] = True
    categories=[("Manufacturing",("manufactur","factory","निर्माण")),("Restaurant",("restaurant","cafe","रेस्टोरेंट")),("Professional offices",("clinic","dental","physio","office","legal","क्लिनिक","दफ्तर")),("Services",("salon","beauty","सेलून")),("Retail",("shop","kirana","store","retail","दुकान"))]
    detected=next((label for label,terms in categories if any(term in low for term in terms)),None)
    if detected:profile["business_type"]=detected
    elif not profile.get("business_type"):profile["business_type"]="Services"
    employee=re.search(r"(\d{1,4})\s*(?:employees?|people|staff|workers?|कर्मचारी)",low)
    site_count=re.search(r"(\d{1,3})\s*(?:sites?|locations?|branches|outlets?|जगह|शाखाएँ)",low)
    if employee:profile["employees"]=int(employee.group(1))
    if site_count:profile["sites"]=int(site_count.group(1))
    for city,(city_name,tier) in sorted(_cities().items(),key=lambda item:len(item[0]),reverse=True):
        if city in low:profile["city"]=city_name;profile["city_tier"]=tier;break
    if not profile.get("employees"): profile["employees"] = 4
    if not profile.get("sites"): profile["sites"] = 1
    if not profile.get("city"): profile["city"] = "Nagpur"
    if profile.get("has_gstin") not in ("Y", "N"): profile["has_gstin"] = "N"
    profile.setdefault("city_tier", 2)
    mobile_only = any(x in low for x in ("mobile only", "only mobile", "सिर्फ मोबाइल"))
    if mobile_only: profile["mobile_only"] = True
    no_gstin = any(x in low for x in ("no gst", "without gst", "gstin nahi", "जीएसटी नहीं", "बिना जीएसटी"))
    if no_gstin:
        profile["has_gstin"] = "N"; profile.pop("gstin", None)
    elif any(x in low for x in ("gstin", "gst hai", "gst yes")):
        profile["has_gstin"] = "Y"; profile.setdefault("gstin", "32TTNXB7384T1ZW")
    bundle = recommend_bundle(profile)
    q = quote(bundle, profile=profile)
    third_en="An active GSTIN can unlock more services." if profile.get("has_gstin")!="Y" else "You can add services as the business grows."
    third_hi="सक्रिय GSTIN से और सेवाएँ खुल सकती हैं।" if profile.get("has_gstin")!="Y" else "व्यवसाय बढ़ने पर सेवाएँ जोड़ सकते हैं।"
    why_en = [f"Sized for a {profile['business_type'].lower()} business.", f"Covers {profile['sites']} location(s) in {profile['city']}.", third_en]
    why_hi = [f"यह {profile['business_type']} कारोबार के हिसाब से है।", f"{profile['city']} में आपकी {profile['sites']} जगह के लिए बनाया गया है।", third_hi]
    if lang == "hi":
        reply = f"आपके लिए एक शुरुआती कनेक्टिविटी पैक तैयार है। अनुमानित मासिक कीमत ₹{q['expected_monthly']:,} है। क्या मैं इसका पूरा कोट दिखाऊँ?"
    else: reply = f"I’ve prepared a practical starter bundle. The expected monthly total is ₹{q['expected_monthly']:,}. Would you like to review the quote?"
    if profile.get("price_objection"):
        reply = (f"मैंने कम कीमत वाला पात्र विकल्प चुना है। अनुमानित मासिक कीमत ₹{q['expected_monthly']:,} है।"
                 if lang == "hi" else
                 f"I’ve switched to a lower-cost eligible option. The expected monthly total is ₹{q['expected_monthly']:,}.")
    generated=_gemini_reply(message,lang,profile,bundle,q) if _configured_key() else None
    if generated:reply=generated
    return {"reply":reply,"language":lang,"profile":profile,"bundle":bundle,"quote":q,"why":why_hi if lang=="hi" else why_en,"questions_used":min(5,sum(bool(profile.get(k)) for k in ("business_type","employees","sites","city","has_gstin")))}
