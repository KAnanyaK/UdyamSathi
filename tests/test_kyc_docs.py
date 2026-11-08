from pathlib import Path
import re

def test_all_provided_kyc_fixtures_are_enumerated_as_synthetic():
    folder=Path(__file__).resolve().parents[1]/"data"/"kyc_documents"
    images=sorted(folder.glob("*.png"))
    assert len(images)==47
    assert all(re.match(r"K\d{2}_(?:gst_certificate|udyam_certificate|signatory_id|address_proof)\.png$",p.name) for p in images)
