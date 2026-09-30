from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
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

@api_router.get("/dashboard")
async def dashboard():
    accounts = await db.accounts.find({}, {"_id": 0}).to_list(100)
    transactions = await db.transactions.find({}, {"_id": 0}).sort("due_date", -1).to_list(1000)
    total = sum(a["balance"] for a in accounts)
    income = sum(t["amount"] for t in transactions if t["kind"] == "income")
    expense = sum(t["amount"] for t in transactions if t["kind"] == "expense")
    pending = [t for t in transactions if t.get("status") == "Bekliyor"]
    return {"accounts": accounts, "transactions": transactions, "summary": {"balance": total, "income": income, "expense": expense, "pending": sum(t["amount"] for t in pending), "pending_count": len(pending)}}

@api_router.get("/accounts", response_model=List[Account])
async def get_accounts():
    return await db.accounts.find({}, {"_id": 0}).to_list(100)

@api_router.post("/accounts", response_model=Account)
async def create_account(input: AccountCreate):
    item = Account(**input.model_dump())
    await db.accounts.insert_one(item.model_dump())
    return item

@api_router.delete("/accounts/{item_id}")
async def delete_account(item_id: str):
    result = await db.accounts.delete_one({"id": item_id})
    if not result.deleted_count: raise HTTPException(404, "Hesap bulunamadı")
    return {"ok": True}

@api_router.get("/transactions", response_model=List[Transaction])
async def get_transactions():
    return await db.transactions.find({}, {"_id": 0}).sort("due_date", -1).to_list(1000)

@api_router.post("/transactions", response_model=Transaction)
async def create_transaction(input: TransactionCreate):
    item = Transaction(**input.model_dump())
    await db.transactions.insert_one(item.model_dump())
    return item

@api_router.delete("/transactions/{item_id}")
async def delete_transaction(item_id: str):
    result = await db.transactions.delete_one({"id": item_id})
    if not result.deleted_count: raise HTTPException(404, "Kayıt bulunamadı")
    return {"ok": True}

@api_router.post("/transactions/import")
async def import_transactions(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    created = []
    for row in rows:
        item = TransactionCreate(kind=row.get("kind", "expense"), title=row.get("title", "İçe aktarılan kayıt"), category=row.get("category", "Diğer"), amount=float(row.get("amount", 0)), currency=row.get("currency", "TRY"), account=row.get("account", "İşletme Hesabı"), due_date=row.get("due_date", date.today().isoformat()), status=row.get("status", "Tamamlandı"))
        obj = Transaction(**item.model_dump()); await db.transactions.insert_one(obj.model_dump()); created.append(obj)
    return {"created": len(created)}

@api_router.get("/reports")
async def reports():
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(1000)
    categories = {}
    for t in transactions:
        if t["kind"] == "expense": categories[t["category"]] = categories.get(t["category"], 0) + t["amount"]
    return {"categories": [{"name": k, "value": v} for k, v in categories.items()], "monthly": [{"month": "Oca", "income": 124000, "expense": 84000}, {"month": "Şub", "income": 158000, "expense": 102000}, {"month": "Mar", "income": 209600, "expense": 53650}]}

@app.on_event("startup")
async def startup(): await seed_data()
app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO)

@app.on_event("shutdown")
async def shutdown_db_client(): client.close()