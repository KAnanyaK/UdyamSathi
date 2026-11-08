"""Print three demo profiles; all identifiers are synthetic placeholders."""
import json
from pathlib import Path
PERSONAS=[
 {"name":"Kirana owner","profile":{"business_type":"Retail","employees":4,"sites":1,"city":"Nagpur","city_tier":2,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW","preferred_language":"hi"}},
 {"name":"Salon owner","profile":{"business_type":"Services","employees":3,"sites":1,"city":"Jaipur","city_tier":2,"has_gstin":"N","preferred_language":"hi"}},
 {"name":"Restaurant chain","profile":{"business_type":"Restaurant","employees":35,"sites":3,"city":"Mumbai","city_tier":1,"has_gstin":"Y","gstin":"32TTNXB7384T1ZW","preferred_language":"en"}},
]
if __name__=="__main__":
    target=Path(__file__).resolve().parents[1]/"data"/"demo_personas.json"
    target.write_text(json.dumps(PERSONAS,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Seeded {len(PERSONAS)} synthetic personas to {target}")
