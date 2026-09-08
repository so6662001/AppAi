from client_guard import approval

S = "unit-secret"


def test_issue_verify_roundtrip():
    tok = approval.issue(S, 1001, 1023, "sales_order", 10000, 4_000_000_000, "李经理", nonce="abcd1234")
    assert tok.count(".") == 1
    r = approval.verify(S, tok, tenant_id=1001, user_id=1023, data_set="SALES_ORDER", row_count=9000, now=1_800_000_000)
    assert r.valid and r.approver == "李经理" and r.max_rows == 10000 and r.nonce == "abcd1234"


def test_verify_failures():
    tok = approval.issue(S, 1, 2, "so", 100, 4_000_000_000, "a")
    assert approval.verify("bad", tok).error == "signature"
    assert approval.verify(S, tok, tenant_id=9).error == "tenant"
    assert approval.verify(S, tok, user_id=9).error == "user"
    assert approval.verify(S, tok, data_set="x").error == "dataset"
    assert approval.verify(S, tok, row_count=101).error == "rows"
    assert approval.verify(S, tok, now=4_000_000_001).error == "expired"
    assert approval.verify(S, "garbage").error == "format"
    assert approval.verify(S, "a.b!!").error in ("base64", "signature")


def test_known_vector_matches_csharp():
    """固定向量:C# 端 ApprovalTokenVerifier 单测使用同一字符串,保证跨语言兼容."""
    tok = approval.issue("cross-lang-secret", 1001, 1023, "sales_order", 5000, 1_900_000_000, "王总", nonce="deadbeef")
    assert tok == (
        "MTAwMXwxMDIzfHNhbGVzX29yZGVyfDUwMDB8MTkwMDAwMDAwMHznjovmgLt8ZGVhZGJlZWY."
        "4zgUDwUnEAc4_gdfWoanQX65uO2U4Z_OErfgOTZqP18"
    )
