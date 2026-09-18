import hashlib
import json
import unittest
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import requirements
from experiments.edge_ipo_bridge import (
    import_edge_ipo_export,
    verify_edge_ipo_shared_bundle,
)

NOW=datetime(2026,9,18,7,30,tzinfo=timezone.utc)
SUBJECT={"id":"fixture-ipo-202609","name":"Fixture Limited","segment":"MAINBOARD"}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make_export(state_overrides=None):
    state_overrides=state_overrides or {}
    evidence=[]
    for row in requirements("EDGE_IPO"):
        variable=row["variable_id"]
        evidence.append({
            "variable_id":variable,
            "status":state_overrides.get(variable,"COMPLETE"),
            "values":{"fixture":variable},
            "sources":[{
                "name":"SEBI",
                "url":"https://www.sebi.gov.in/"+variable.lower(),
                "source_type":"OFFICIAL_REGULATORY",
                "authority":1,
                "source_sha256":digest(variable),
                "published_at":NOW.isoformat(),
                "retrieved_at":NOW.isoformat(),
            }],
            "observed_at":NOW.isoformat(),
            "notes":None,
        })
    body={
        "schema":"edge-ipo-shared-evidence-export-v1",
        "consumer":"EDGE_IPO",
        "subject":SUBJECT.copy(),
        "namespace":"EDGE_IPO:"+SUBJECT["id"],
        "run_id":"IPO-EDGE-FIXTURE-1",
        "frozen_at":NOW.isoformat(),
        "status":"READY",
        "coverage":{
            "required_variables":[r["variable_id"] for r in requirements("EDGE_IPO")],
            "variables_present":sorted(r["variable_id"] for r in requirements("EDGE_IPO")),
            "missing_variables":[],
            "unresolved_variables":[],
        },
        "evidence":evidence,
        "source_health":[],
        "methodology_applied":False,
        "scoring_applied":False,
        "grade_assigned":False,
        "recommendation_generated":False,
        "learning_promoted":False,
        "historical_checkpoint_write_enabled":False,
        "trading_enabled":False,
    }
    body["bundle_sha256"]=hashlib.sha256(
        json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()
    ).hexdigest()
    return body


class EdgeIpoBridgeTests(unittest.TestCase):
    def test_ready_export_becomes_ready_shared_bundle(self):
        bundle=import_edge_ipo_export(make_export({
            "IPO_BROKER_RESEARCH":"VERIFIED_PARTIAL",
            "IPO_GMP":"RECOVERED_VIA_FALLBACK",
        }))
        self.assertEqual(bundle["status"],"READY")
        self.assertEqual(bundle["consumer"],"EDGE_IPO")
        self.assertEqual(bundle["subject"]["id"],SUBJECT["id"])
        self.assertEqual(bundle["coverage"]["missing_variables"],[])
        self.assertFalse(bundle["derived_evidence"]["methodology_applied"])
        self.assertEqual(
            bundle["derived_evidence"]["evidence_states"]["IPO_GMP"],
            "RECOVERED_VIA_FALLBACK",
        )
        self.assertEqual(verify_edge_ipo_shared_bundle(bundle)["consumer"],"EDGE_IPO")

    def test_conflicted_or_unavailable_evidence_rejected(self):
        for state in ("CONFLICTED","UNAVAILABLE"):
            with self.subTest(state=state):
                with self.assertRaises(DataArchitectureError):
                    import_edge_ipo_export(make_export({"IPO_FINANCIALS":state}))

    def test_blocked_export_rejected(self):
        export=make_export()
        export["status"]="BLOCKED"
        body={k:v for k,v in export.items() if k!="bundle_sha256"}
        export["bundle_sha256"]=hashlib.sha256(
            json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()
        ).hexdigest()
        with self.assertRaises(DataArchitectureError):
            import_edge_ipo_export(export)

    def test_methodology_or_grade_leakage_rejected(self):
        for flag in ("methodology_applied","scoring_applied","grade_assigned","recommendation_generated"):
            export=make_export()
            export[flag]=True
            body={k:v for k,v in export.items() if k!="bundle_sha256"}
            export["bundle_sha256"]=hashlib.sha256(
                json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()
            ).hexdigest()
            with self.subTest(flag=flag):
                with self.assertRaises(DataArchitectureError):
                    import_edge_ipo_export(export)

    def test_tampered_export_rejected(self):
        export=make_export()
        export["subject"]["name"]="Tampered"
        with self.assertRaisesRegex(DataArchitectureError,"fingerprint"):
            import_edge_ipo_export(export)


if __name__=="__main__":
    unittest.main()
