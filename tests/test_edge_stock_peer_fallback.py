import unittest
from datetime import datetime, timezone

from experiments.edge_stock_peer_fallback import acquire_peer_fallback
from experiments.edge_stock_source_registry import build_source_health, source_registry
from experiments.data_contract import DataArchitectureError

NOW=datetime(2026,9,18,7,30,tzinfo=timezone.utc)
STOCK={
    "kind":"STOCK","id":"INE498L01015","name":"L&T Finance Ltd",
    "exchange":"NSE","segment":"NSE_EQ","instrument_key":"NSE_EQ|INE498L01015",
    "symbol":"LTF","isin":"INE498L01015",
}


class Response:
    def __init__(self, body): self.body=body.encode()
    def read(self,n=-1): return self.body if n<0 else self.body[:n]
    def __enter__(self): return self
    def __exit__(self,*args): return False


class Opener:
    def __init__(self): self.urls=[]
    def open(self,request,timeout=20):
        self.urls.append(request.full_url)
        if "/company/" in request.full_url:
            return Response("""
            <html><h2>Peer comparison</h2>
            <a href="/market/IN05/">Financial Services</a>
            <a href="/market/IN05/IN0501/IN050101/IN050101004/">NBFC</a>
            </html>""")
        return Response("""
        <html><table>
        <tr><td><a href="/company/BAJFINANCE/">Bajaj Finance</a></td></tr>
        <tr><td><a href="/company/SHRIRAMFIN/">Shriram Finance</a></td></tr>
        <tr><td><a href="/company/CHOLAFIN/">Chola Finance</a></td></tr>
        <tr><td><a href="/company/LTF/">L&amp;T Finance</a></td></tr>
        <tr><td><a href="/company/MUTHOOTFIN/">Muthoot Finance</a></td></tr>
        </table></html>""")


class PeerFallbackTests(unittest.TestCase):
    def test_registry_contains_governed_sources(self):
        rows=source_registry()
        self.assertEqual(rows["NSE_ANNOUNCEMENTS"]["authority"],"OFFICIAL")
        self.assertEqual(rows["SEBI_ORDERS"]["type"],"REGULATORY")
        self.assertEqual(rows["SCREENER_PEER_COHORT"]["authority"],"SECONDARY")

    def test_peer_fallback_builds_recovered_record(self):
        record=acquire_peer_fallback(STOCK,acquisition_timestamp=NOW,opener=Opener())
        self.assertEqual(record["variable_id"],"STOCK_PEERS")
        self.assertEqual(record["values"]["reconciliation_status"],"RECOVERED_VIA_FALLBACK")
        self.assertEqual(record["values"]["industry"],"NBFC")
        self.assertEqual(record["values"]["peer_count"],4)
        self.assertTrue(record["eligible_for_consumer"])

    def test_source_health_rejects_wrong_domain(self):
        with self.assertRaises(DataArchitectureError):
            build_source_health(
                source_name="SEBI_ORDERS",url="https://example.com/x",
                checked_at=NOW,success=True,
            )


if __name__=="__main__": unittest.main()
