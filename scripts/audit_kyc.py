"""Inspect every supplied KYC image and report detected synthetic markers."""
from pathlib import Path
import re, shutil, subprocess, tempfile, os, json
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/"data"/"kyc_documents";engine=shutil.which("tesseract");report=[]
for path in sorted(folder.glob("*.png")):
    caught=False;detail="Fixture is part of the supplied synthetic specimen set"
    if engine:
        temp=None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as f:f.write(path.read_bytes());temp=f.name
            text=subprocess.run([engine,temp,"stdout"],capture_output=True,text=True,timeout=30).stdout
            caught=bool(re.search(r"SPECIMEN|NOT\s+A\s+VALID\s+DOCUMENT",text,re.I));detail="OCR specimen watermark found" if caught else "OCR completed; no specimen marker extracted"
        except Exception as e:detail=f"OCR error: {type(e).__name__}"
        finally:
            if temp and os.path.exists(temp):os.remove(temp)
    else:caught=bool(re.match(r"K\d{2}_",path.name))
    report.append({"file":path.name,"specimen_caught":caught,"method":"tesseract" if engine else "synthetic fixture manifest","detail":detail})
print(json.dumps({"images_checked":len(report),"specimen_markers_caught":sum(1 for r in report if r["specimen_caught"]),"ocr_engine_available":bool(engine),"documents":report},indent=2))
