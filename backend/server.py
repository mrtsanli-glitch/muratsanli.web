from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, date, timedelta
import os, uuid, csv, io, logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI()
api_router = APIRouter(prefix="/api")


# ---------- Models ----------
class Account(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str = "Banka"
    currency: str = "TRY"
    balance: float = 0
    color: str = "emerald"

class AccountCreate(BaseModel):
    name: str
    type: str = "Banka"
    currency: str = "TRY"
    balance: float = 0
    color: str = "emerald"

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    currency: Optional[str] = None
    balance: Optional[float] = None
    color: Optional[str] = None


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str = "Müşteri"  # Müşteri / Tedarikçi
    balance: float = 0     # + alacak, - borç
    currency: str = "TRY"
    due_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None

class ContactCreate(BaseModel):
    name: str
    type: str = "Müşteri"
    balance: float = 0
    currency: str = "TRY"
    due_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    balance: Optional[float] = None
    currency: Optional[str] = None
    due_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str
    title: str
    category: str
    amount: float
    currency: str = "TRY"
    account: str
    contact: Optional[str] = None
    due_date: str
    status: str = "Tamamlandı"
    note: Optional[str] = None

class TransactionCreate(BaseModel):
    kind: str
    title: str
    category: str
    amount: float
    currency: str = "TRY"
    account: str
    contact: Optional[str] = None
    due_date: str
    status: str = "Tamamlandı"
    note: Optional[str] = None


# ---------- Seed ----------
async def seed_data():
    if await db.accounts.count_documents({}) == 0:
        await db.accounts.insert_many([
            Account(id="acc-1", name="İşletme Hesabı", type="Banka", currency="TRY", balance=184250, color="emerald").model_dump(),
            Account(id="acc-2", name="Vadeli Mevduat", type="Banka", currency="TRY", balance=96500, color="blue").model_dump(),
            Account(id="acc-3", name="Kasa", type="Kasa", currency="TRY", balance=12750, color="amber").model_dump(),
        ])
    if await db.transactions.count_documents({}) == 0:
        today = date.today()
        demo = [
            Transaction(id="tx-1", kind="income", title="Mart satışları", category="Satış", amount=128400, account="İşletme Hesabı", contact="Nova Teknoloji", due_date=(today - timedelta(days=2)).isoformat()).model_dump(),
            Transaction(id="tx-2", kind="expense", title="Ofis kirası", category="Ofis", amount=28500, account="İşletme Hesabı", due_date=(today + timedelta(days=4)).isoformat(), status="Bekliyor").model_dump(),
            Transaction(id="tx-3", kind="income", title="Danışmanlık hizmeti", category="Hizmet", amount=46200, account="İşletme Hesabı", contact="Mavi Şirketler", due_date=(today + timedelta(days=8)).isoformat(), status="Bekliyor").model_dump(),
            Transaction(id="tx-4", kind="expense", title="Bulut servisleri", category="Abonelik", amount=6400, account="İşletme Hesabı", due_date=(today - timedelta(days=5)).isoformat()).model_dump(),
            Transaction(id="tx-5", kind="expense", title="Tedarikçi ödemesi", category="Tedarik", amount=18750, account="İşletme Hesabı", contact="Atlas Tedarik", due_date=(today + timedelta(days=12)).isoformat(), status="Bekliyor").model_dump(),
            Transaction(id="tx-6", kind="income", title="Proje avansı", category="Hizmet", amount=35000, account="İşletme Hesabı", contact="Kuzey Ajans", due_date=(today - timedelta(days=12)).isoformat()).model_dump(),
        ]
        await db.transactions.insert_many(demo)
    if await db.contacts.count_documents({}) == 0:
        today = date.today()
        demo = [
            Contact(id="ct-1", name="Nova Teknoloji", type="Müşteri", balance=68400, currency="TRY", due_date=(today + timedelta(days=6)).isoformat(), phone="+90 555 010 2245", email="finans@nova.co").model_dump(),
            Contact(id="ct-2", name="Mavi Şirketler", type="Müşteri", balance=24800, currency="TRY", due_date=(today - timedelta(days=3)).isoformat(), phone="+90 555 448 3271").model_dump(),
            Contact(id="ct-3", name="Atlas Tedarik", type="Tedarikçi", balance=-18750, currency="TRY", due_date=(today + timedelta(days=12)).isoformat(), phone="+90 555 900 1122").model_dump(),
            Contact(id="ct-4", name="Kuzey Ajans", type="Müşteri", balance=12500, currency="TRY", due_date=(today + timedelta(days=32)).isoformat()).model_dump(),
        ]
        await db.contacts.insert_many(demo)


# ---------- Dashboard ----------
@api_router.get("/dashboard")
async def dashboard():
    accounts = await db.accounts.find({}, {"_id": 0}).to_list(500)
    transactions = await db.transactions.find({}, {"_id": 0}).sort("due_date", -1).to_list(2000)
    contacts = await db.contacts.find({}, {"_id": 0}).to_list(500)
    total = sum(a["balance"] for a in accounts)
    current_month = date.today().strftime("%Y-%m")
    month_transactions = [t for t in transactions if t.get("due_date", "").startswith(current_month)]
    income = sum(t["amount"] for t in month_transactions if t["kind"] == "income")
    expense = sum(t["amount"] for t in month_transactions if t["kind"] == "expense")
    pending = [t for t in transactions if t.get("status") == "Bekliyor"]
    return {
        "accounts": accounts,
        "transactions": transactions,
        "contacts": contacts,
        "summary": {
            "balance": total,
            "income": income,
            "expense": expense,
            "pending": sum(t["amount"] for t in pending),
            "pending_count": len(pending),
            "receivable": sum(c["balance"] for c in contacts if c["balance"] > 0),
            "payable": -sum(c["balance"] for c in contacts if c["balance"] < 0),
        },
    }


# ---------- Accounts ----------
@api_router.get("/accounts", response_model=List[Account])
async def get_accounts():
    return await db.accounts.find({}, {"_id": 0}).to_list(500)

@api_router.post("/accounts", response_model=Account)
async def create_account(input: AccountCreate):
    item = Account(**input.model_dump())
    await db.accounts.insert_one(item.model_dump())
    return item

@api_router.patch("/accounts/{item_id}", response_model=Account)
async def update_account(item_id: str, patch: AccountUpdate):
    existing = await db.accounts.find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Hesap bulunamadı")
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    if "name" in changes and changes["name"] != existing["name"]:
        await db.transactions.update_many({"account": existing["name"]}, {"$set": {"account": changes["name"]}})
    updated = {**existing, **changes}
    await db.accounts.update_one({"id": item_id}, {"$set": changes})
    return Account(**updated)

@api_router.delete("/accounts/{item_id}")
async def delete_account(item_id: str):
    result = await db.accounts.delete_one({"id": item_id})
    if not result.deleted_count:
        raise HTTPException(404, "Hesap bulunamadı")
    return {"ok": True}


# ---------- Contacts (Cari) ----------
@api_router.get("/contacts", response_model=List[Contact])
async def get_contacts():
    return await db.contacts.find({}, {"_id": 0}).to_list(500)

@api_router.post("/contacts", response_model=Contact)
async def create_contact(input: ContactCreate):
    item = Contact(**input.model_dump())
    await db.contacts.insert_one(item.model_dump())
    return item

@api_router.patch("/contacts/{item_id}", response_model=Contact)
async def update_contact(item_id: str, patch: ContactUpdate):
    existing = await db.contacts.find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Cari bulunamadı")
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    updated = {**existing, **changes}
    await db.contacts.update_one({"id": item_id}, {"$set": changes})
    return Contact(**updated)

@api_router.delete("/contacts/{item_id}")
async def delete_contact(item_id: str):
    result = await db.contacts.delete_one({"id": item_id})
    if not result.deleted_count:
        raise HTTPException(404, "Cari bulunamadı")
    return {"ok": True}


# ---------- Transactions ----------
@api_router.get("/transactions", response_model=List[Transaction])
async def get_transactions():
    return await db.transactions.find({}, {"_id": 0}).sort("due_date", -1).to_list(2000)

@api_router.post("/transactions", response_model=Transaction)
async def create_transaction(input: TransactionCreate):
    item = Transaction(**input.model_dump())
    await db.transactions.insert_one(item.model_dump())
    delta = item.amount if item.kind == "income" else -item.amount
    await db.accounts.update_one({"name": item.account}, {"$inc": {"balance": delta}})
    return item

@api_router.delete("/transactions/{item_id}")
async def delete_transaction(item_id: str):
    existing = await db.transactions.find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Kayıt bulunamadı")
    await db.transactions.delete_one({"id": item_id})
    delta = existing["amount"] if existing["kind"] == "income" else -existing["amount"]
    await db.accounts.update_one({"name": existing["account"]}, {"$inc": {"balance": -delta}})
    return {"ok": True}

@api_router.post("/transactions/import")
async def import_transactions(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    created = []
    for row in rows:
        item = TransactionCreate(
            kind=row.get("kind", "expense"),
            title=row.get("title", "İçe aktarılan kayıt"),
            category=row.get("category", "Diğer"),
            amount=float(row.get("amount", 0)),
            currency=row.get("currency", "TRY"),
            account=row.get("account", "İşletme Hesabı"),
            due_date=row.get("due_date", date.today().isoformat()),
            status=row.get("status", "Tamamlandı"),
        )
        obj = Transaction(**item.model_dump())
        await db.transactions.insert_one(obj.model_dump())
        delta = obj.amount if obj.kind == "income" else -obj.amount
        await db.accounts.update_one({"name": obj.account}, {"$inc": {"balance": delta}})
        created.append(obj)
    return {"created": len(created)}


# ---------- Reports ----------
@api_router.get("/reports")
async def reports():
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(2000)
    categories = {}
    monthly = {}
    for t in transactions:
        if t["kind"] == "expense":
            categories[t["category"]] = categories.get(t["category"], 0) + t["amount"]
        month = t.get("due_date", "")[:7]
        if month:
            monthly.setdefault(month, {"income": 0, "expense": 0})[t["kind"]] += t["amount"]
    labels = {1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz", 7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"}
    ordered = sorted(monthly.items())[-6:]
    return {
        "categories": [{"name": k, "value": v} for k, v in categories.items()],
        "monthly": [{"month": labels.get(int(m[5:7]), m), **values} for m, values in ordered],
    }


def _aging_buckets():
    return {"overdue": 0, "d0_7": 0, "d8_30": 0, "d30_plus": 0}

@api_router.get("/reports/aging")
async def aging_report():
    """Cari vade yaşlandırma raporu — carilerin vade tarihine göre segmentleri."""
    contacts = await db.contacts.find({}, {"_id": 0}).to_list(500)
    today = date.today()
    receivable = _aging_buckets()
    payable = _aging_buckets()
    rows = []
    for c in contacts:
        due = c.get("due_date")
        bal = c.get("balance", 0)
        if not bal:
            continue
        days = None
        bucket = "no_due"
        if due:
            try:
                d = date.fromisoformat(due)
                days = (d - today).days
                if days < 0:
                    bucket = "overdue"
                elif days <= 7:
                    bucket = "d0_7"
                elif days <= 30:
                    bucket = "d8_30"
                else:
                    bucket = "d30_plus"
            except ValueError:
                pass
        target = receivable if bal > 0 else payable
        if bucket in target:
            target[bucket] += abs(bal)
        rows.append({
            "id": c["id"],
            "name": c["name"],
            "type": c["type"],
            "balance": bal,
            "currency": c.get("currency", "TRY"),
            "due_date": due,
            "days": days,
            "bucket": bucket,
        })
    rows.sort(key=lambda r: (r["days"] if r["days"] is not None else 9999))
    return {"rows": rows, "receivable": receivable, "payable": payable}


def _csv_response(filename: str, headers: list, rows: list):
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel Turkish chars
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@api_router.get("/reports/export/cashflow")
async def export_cashflow():
    transactions = await db.transactions.find({}, {"_id": 0}).sort("due_date", 1).to_list(2000)
    rows = [
        [t.get("due_date", ""), "Gelir" if t["kind"] == "income" else "Gider",
         t.get("title", ""), t.get("category", ""), t.get("account", ""),
         t.get("contact", "") or "", t.get("amount", 0), t.get("currency", "TRY"),
         t.get("status", "")]
        for t in transactions
    ]
    return _csv_response("nakit-akisi.csv",
                         ["Tarih", "Tür", "İşlem", "Kategori", "Hesap", "Cari", "Tutar", "Para Birimi", "Durum"],
                         rows)

@api_router.get("/reports/export/aging")
async def export_aging():
    data = await aging_report()
    label = {"overdue": "Gecikmiş", "d0_7": "0-7 gün", "d8_30": "8-30 gün", "d30_plus": "30+ gün", "no_due": "Vade yok"}
    rows = [
        [r["name"], r["type"], r["balance"], r.get("currency", "TRY"),
         r.get("due_date") or "", r.get("days") if r.get("days") is not None else "",
         label.get(r["bucket"], r["bucket"])]
        for r in data["rows"]
    ]
    return _csv_response("cari-vade.csv",
                         ["Cari", "Tür", "Bakiye", "Para Birimi", "Vade", "Kalan Gün", "Segment"],
                         rows)


# ---------- App wiring ----------
@app.on_event("startup")
async def startup():
    await seed_data()

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
