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
    assert {"balance", "income", "expense", "pending", "pending_count"} <= data["summary"].keys()


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