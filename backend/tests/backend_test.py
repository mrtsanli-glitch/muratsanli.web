"""Regression tests for dashboard, accounts, transactions, import, and reports APIs."""
import os
import uuid
from datetime import date

import pytest
import requests


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture
def client():
    with requests.Session() as session:
        yield session


def test_dashboard_shape(client):
    response = client.get(f"{BASE_URL}/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["accounts"], list)
    assert isinstance(data["transactions"], list)
    assert {"balance", "income", "expense", "pending", "pending_count", "receivable", "payable"} <= data["summary"].keys()
    assert isinstance(data["contacts"], list)
    assert isinstance(data["summary"]["receivable"], (int, float))
    assert isinstance(data["summary"]["payable"], (int, float))


def test_accounts_endpoint(client):
    response = client.get(f"{BASE_URL}/api/accounts")
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) >= 1
    assert {"id", "name", "currency", "balance"} <= accounts[0].keys()


def test_reports_endpoint(client):
    response = client.get(f"{BASE_URL}/api/reports")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["categories"], list)
    assert isinstance(data["monthly"], list)
    assert {"month", "income", "expense"} <= data["monthly"][0].keys()


def test_transaction_create_and_delete(client):
    title = f"TEST_{uuid.uuid4().hex[:8]}"
    payload = {
        "kind": "income",
        "title": title,
        "category": "Satış",
        "amount": 123.45,
        "currency": "TRY",
        "account": "İşletme Hesabı",
        "due_date": "2025-03-18",
        "status": "Tamamlandı",
    }
    created = client.post(f"{BASE_URL}/api/transactions", json=payload)
    assert created.status_code == 200
    item = created.json()
    assert item["title"] == title
    assert isinstance(item["id"], str)

    listed = client.get(f"{BASE_URL}/api/transactions")
    assert listed.status_code == 200
    assert any(row["id"] == item["id"] and row["title"] == title for row in listed.json())

    deleted = client.delete(f"{BASE_URL}/api/transactions/{item['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert not any(row["id"] == item["id"] for row in client.get(f"{BASE_URL}/api/transactions").json())


def test_transaction_mutation_reconciles_dashboard_and_account(client):
    account_name = "İşletme Hesabı"
    before_dashboard = client.get(f"{BASE_URL}/api/dashboard").json()
    before_account = next(a for a in before_dashboard["accounts"] if a["name"] == account_name)
    title = f"TEST_balance_{uuid.uuid4().hex[:8]}"
    payload = {
        "kind": "income", "title": title, "category": "Satış", "amount": 77.25,
        "currency": "TRY", "account": account_name, "due_date": date.today().isoformat(),
        "status": "Tamamlandı",
    }
    created = client.post(f"{BASE_URL}/api/transactions", json=payload)
    assert created.status_code == 200
    after_create = client.get(f"{BASE_URL}/api/dashboard").json()
    after_account = next(a for a in after_create["accounts"] if a["name"] == account_name)
    assert after_account["balance"] == pytest.approx(before_account["balance"] + 77.25)
    assert after_create["summary"]["income"] == pytest.approx(before_dashboard["summary"]["income"] + 77.25)
    deleted = client.delete(f"{BASE_URL}/api/transactions/{created.json()['id']}")
    assert deleted.status_code == 200
    restored = client.get(f"{BASE_URL}/api/dashboard").json()
    restored_account = next(a for a in restored["accounts"] if a["name"] == account_name)
    assert restored_account["balance"] == pytest.approx(before_account["balance"])
    assert restored["summary"]["income"] == pytest.approx(before_dashboard["summary"]["income"])


def test_reports_include_persisted_current_month_transaction(client):
    title = f"TEST_report_{uuid.uuid4().hex[:8]}"
    payload = {
        "kind": "expense", "title": title, "category": "TEST_Rapor", "amount": 88.5,
        "currency": "TRY", "account": "İşletme Hesabı", "due_date": date.today().isoformat(),
        "status": "Tamamlandı",
    }
    created = client.post(f"{BASE_URL}/api/transactions", json=payload)
    assert created.status_code == 200
    try:
        report = client.get(f"{BASE_URL}/api/reports").json()
        month_labels = {1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz", 7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"}
        current_month = month_labels[date.today().month]
        assert any(row["month"] == current_month and row["expense"] >= 88.5 for row in report["monthly"])
        assert any(row["name"] == "TEST_Rapor" and row["value"] >= 88.5 for row in report["categories"])
    finally:
        client.delete(f"{BASE_URL}/api/transactions/{created.json()['id']}")


def test_csv_import(client):
    csv_text = "kind,title,category,amount,currency,account,due_date,status\nexpense,TEST_import,Ofis,9.5,TRY,İşletme Hesabı,2025-03-18,Tamamlandı\n"
    response = client.post(
        f"{BASE_URL}/api/transactions/import",
        files={"file": ("test.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1


# ---------- Accounts CRUD ----------
def test_account_create_patch_rename_cascade_and_delete(client):
    unique = uuid.uuid4().hex[:8]
    name = f"TEST_acc_{unique}"
    create = client.post(f"{BASE_URL}/api/accounts", json={
        "name": name, "type": "Banka", "currency": "TRY", "balance": 1000, "color": "blue",
    })
    assert create.status_code == 200
    acc = create.json()
    assert acc["name"] == name and acc["balance"] == 1000

    # verify GET
    listed = client.get(f"{BASE_URL}/api/accounts").json()
    assert any(a["id"] == acc["id"] for a in listed)

    # Create a transaction referencing this account
    tx = client.post(f"{BASE_URL}/api/transactions", json={
        "kind": "income", "title": f"TEST_tx_{unique}", "category": "Satış",
        "amount": 500, "currency": "TRY", "account": name,
        "due_date": date.today().isoformat(), "status": "Tamamlandı",
    })
    assert tx.status_code == 200
    tx_id = tx.json()["id"]

    # PATCH rename should cascade to transactions
    new_name = f"TEST_acc_{unique}_renamed"
    patch = client.patch(f"{BASE_URL}/api/accounts/{acc['id']}", json={"name": new_name, "balance": 2500})
    assert patch.status_code == 200
    body = patch.json()
    assert body["name"] == new_name and body["balance"] == 2500

    # verify tx.account got renamed
    all_tx = client.get(f"{BASE_URL}/api/transactions").json()
    renamed_tx = next(t for t in all_tx if t["id"] == tx_id)
    assert renamed_tx["account"] == new_name

    # cleanup
    client.delete(f"{BASE_URL}/api/transactions/{tx_id}")
    deleted = client.delete(f"{BASE_URL}/api/accounts/{acc['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    # 404 on second delete
    assert client.delete(f"{BASE_URL}/api/accounts/{acc['id']}").status_code == 404


def test_account_patch_not_found(client):
    resp = client.patch(f"{BASE_URL}/api/accounts/does-not-exist", json={"name": "x"})
    assert resp.status_code == 404


# ---------- Contacts CRUD ----------
def test_contact_full_crud(client):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "name": f"TEST_contact_{unique}", "type": "Müşteri", "balance": 1500.5,
        "currency": "TRY", "due_date": date.today().isoformat(),
        "phone": "+90 555 000 0000", "email": "test@example.com",
    }
    created = client.post(f"{BASE_URL}/api/contacts", json=payload)
    assert created.status_code == 200
    c = created.json()
    for k in ("id", "name", "type", "balance", "currency", "due_date", "phone", "email"):
        assert k in c
    assert c["name"] == payload["name"] and c["balance"] == 1500.5

    listed = client.get(f"{BASE_URL}/api/contacts")
    assert listed.status_code == 200
    assert any(x["id"] == c["id"] for x in listed.json())

    patched = client.patch(f"{BASE_URL}/api/contacts/{c['id']}", json={"balance": -750, "type": "Tedarikçi"})
    assert patched.status_code == 200
    assert patched.json()["balance"] == -750
    assert patched.json()["type"] == "Tedarikçi"
    # unchanged fields intact
    assert patched.json()["name"] == payload["name"]

    deleted = client.delete(f"{BASE_URL}/api/contacts/{c['id']}")
    assert deleted.status_code == 200
    assert client.delete(f"{BASE_URL}/api/contacts/{c['id']}").status_code == 404


def test_contact_patch_not_found(client):
    resp = client.patch(f"{BASE_URL}/api/contacts/does-not-exist", json={"name": "x"})
    assert resp.status_code == 404


# ---------- Aging report ----------
def test_aging_report_structure_and_buckets(client):
    resp = client.get(f"{BASE_URL}/api/reports/aging")
    assert resp.status_code == 200
    data = resp.json()
    assert {"rows", "receivable", "payable"} <= data.keys()
    for section in ("receivable", "payable"):
        assert {"overdue", "d0_7", "d8_30", "d30_plus"} <= data[section].keys()
    # Rows should contain expected keys
    if data["rows"]:
        row = data["rows"][0]
        assert {"id", "name", "type", "balance", "currency", "due_date", "days", "bucket"} <= row.keys()


def test_aging_report_reflects_created_contact_buckets(client):
    unique = uuid.uuid4().hex[:8]
    # overdue receivable
    r_od = client.post(f"{BASE_URL}/api/contacts", json={
        "name": f"TEST_ag_od_{unique}", "type": "Müşteri", "balance": 1000,
        "due_date": (date.today().fromordinal(date.today().toordinal() - 5)).isoformat(),
    }).json()
    # d0_7 receivable
    r_7 = client.post(f"{BASE_URL}/api/contacts", json={
        "name": f"TEST_ag_7_{unique}", "type": "Müşteri", "balance": 200,
        "due_date": (date.today().fromordinal(date.today().toordinal() + 3)).isoformat(),
    }).json()
    # d30_plus payable
    p_30 = client.post(f"{BASE_URL}/api/contacts", json={
        "name": f"TEST_ag_30_{unique}", "type": "Tedarikçi", "balance": -500,
        "due_date": (date.today().fromordinal(date.today().toordinal() + 45)).isoformat(),
    }).json()
    try:
        report = client.get(f"{BASE_URL}/api/reports/aging").json()
        buckets_by_name = {r["name"]: r["bucket"] for r in report["rows"]}
        assert buckets_by_name[r_od["name"]] == "overdue"
        assert buckets_by_name[r_7["name"]] == "d0_7"
        assert buckets_by_name[p_30["name"]] == "d30_plus"
        assert report["receivable"]["overdue"] >= 1000
        assert report["receivable"]["d0_7"] >= 200
        assert report["payable"]["d30_plus"] >= 500
    finally:
        for cid in (r_od["id"], r_7["id"], p_30["id"]):
            client.delete(f"{BASE_URL}/api/contacts/{cid}")


# ---------- CSV Exports ----------
def test_export_cashflow_csv(client):
    resp = client.get(f"{BASE_URL}/api/reports/export/cashflow")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    text = resp.content.decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "Tarih" in header and "Tutar" in header


def test_export_aging_csv(client):
    resp = client.get(f"{BASE_URL}/api/reports/export/aging")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert resp.content.startswith(b"\xef\xbb\xbf")
    text = resp.content.decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "Cari" in header and "Segment" in header
