"""Regression tests for dashboard, accounts, transactions, import, and reports APIs."""
import os
import uuid

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


def test_csv_import(client):
    csv_text = "kind,title,category,amount,currency,account,due_date,status\nexpense,TEST_import,Ofis,9.5,TRY,İşletme Hesabı,2025-03-18,Tamamlandı\n"
    response = client.post(
        f"{BASE_URL}/api/transactions/import",
        files={"file": ("test.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1