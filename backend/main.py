"""
Kahyata's Consultancy Firm – Payment Backend
Integrates Flutterwave (cards, bank transfers) and MoneyUnify (mobile money).
"""

import os
import uuid
from datetime import datetime

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

load_dotenv()

app = FastAPI(title="Kahyata Payments API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "")
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY", "")
MONEYUNIFY_AUTH_ID = os.getenv("MONEYUNIFY_AUTH_ID", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://kahyata-portfolio-kbkfmiig.devinapps.com")

FLW_BASE = "https://api.flutterwave.com/v3"
MU_BASE = "https://api.moneyunify.one"

# Zambian bank codes (Flutterwave)
ZAMBIAN_BANKS = [
    {"code": "ZM210000", "name": "Zanaco"},
    {"code": "ZM100000", "name": "FNB Zambia"},
    {"code": "ZM040000", "name": "Stanbic Bank Zambia"},
    {"code": "ZM020000", "name": "ABSA Bank Zambia"},
    {"code": "ZM060000", "name": "Atlas Mara Bank"},
    {"code": "ZM080000", "name": "Indo Zambia Bank"},
    {"code": "ZM090000", "name": "Investrust Bank"},
    {"code": "ZM050000", "name": "First Alliance Bank"},
    {"code": "ZM070000", "name": "Access Bank Zambia"},
    {"code": "ZM030000", "name": "Citibank Zambia"},
    {"code": "ZM110000", "name": "United Bank for Africa"},
    {"code": "ZM120000", "name": "Bank of China Zambia"},
]

MOBILE_NETWORKS = [
    {"id": "MTN", "name": "MTN Mobile Money", "prefix": "096, 076"},
    {"id": "AIRTEL", "name": "Airtel Money", "prefix": "097, 077"},
    {"id": "ZAMTEL", "name": "Zamtel Kwacha", "prefix": "095, 075"},
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class MobileMoneyRequest(BaseModel):
    phone_number: str
    network: str  # MTN, AIRTEL, ZAMTEL
    amount: float
    email: str
    fullname: str
    items: list[dict] | None = None


class CardPaymentRequest(BaseModel):
    amount: float
    email: str
    fullname: str
    phone_number: str | None = None
    items: list[dict] | None = None


class BankTransferRequest(BaseModel):
    amount: float
    email: str
    fullname: str
    bank_code: str
    items: list[dict] | None = None


class VerifyRequest(BaseModel):
    reference: str
    gateway: str  # flutterwave or moneyunify


# ---------------------------------------------------------------------------
# Health & Config Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "service": "Kahyata Payments API"}


@app.get("/api/config")
def get_config():
    """Return public config needed by the frontend."""
    return {
        "flutterwave_public_key": FLW_PUBLIC_KEY,
        "banks": ZAMBIAN_BANKS,
        "mobile_networks": MOBILE_NETWORKS,
        "currency": "ZMW",
    }


# ---------------------------------------------------------------------------
# Mobile Money (MoneyUnify – all 3 networks)
# ---------------------------------------------------------------------------
@app.post("/api/pay/mobile-money")
async def pay_mobile_money(req: MobileMoneyRequest):
    """Initiate a mobile money payment via MoneyUnify."""
    if not MONEYUNIFY_AUTH_ID:
        raise HTTPException(503, "MoneyUnify is not configured. Set MONEYUNIFY_AUTH_ID.")

    tx_ref = f"KC-MM-{uuid.uuid4().hex[:12]}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MU_BASE}/payments/request",
            data={
                "from_payer": req.phone_number,
                "amount": str(req.amount),
                "auth_id": MONEYUNIFY_AUTH_ID,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"MoneyUnify error: {resp.text}")

    data = resp.json()
    return {
        "status": "success",
        "gateway": "moneyunify",
        "tx_ref": tx_ref,
        "message": data.get("message", "Payment initiated"),
        "data": data.get("data", {}),
    }


# ---------------------------------------------------------------------------
# Card Payment (Flutterwave Standard – redirect to hosted page)
# ---------------------------------------------------------------------------
@app.post("/api/pay/card")
async def pay_card(req: CardPaymentRequest):
    """Create a Flutterwave Standard payment link for card payments."""
    if not FLW_SECRET_KEY:
        raise HTTPException(503, "Flutterwave is not configured. Set FLW_SECRET_KEY.")

    tx_ref = f"KC-CARD-{uuid.uuid4().hex[:12]}"

    payload = {
        "tx_ref": tx_ref,
        "amount": req.amount,
        "currency": "ZMW",
        "redirect_url": f"{FRONTEND_URL}?payment=success&ref={tx_ref}",
        "customer": {
            "email": req.email,
            "name": req.fullname,
            "phonenumber": req.phone_number or "",
        },
        "customizations": {
            "title": "Kahyata's Consultancy Firm",
            "description": "Payment for tech accessories",
            "logo": "",
        },
        "payment_options": "card",
        "meta": {
            "source": "kahyata-portfolio",
            "items": str(req.items) if req.items else "",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FLW_BASE}/payments",
            json=payload,
            headers={
                "Authorization": f"Bearer {FLW_SECRET_KEY}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"Flutterwave error: {resp.text}")

    data = resp.json()
    return {
        "status": "success",
        "gateway": "flutterwave",
        "tx_ref": tx_ref,
        "payment_link": data.get("data", {}).get("link", ""),
        "message": data.get("message", "Payment link created"),
    }


# ---------------------------------------------------------------------------
# Bank Transfer (Flutterwave)
# ---------------------------------------------------------------------------
@app.post("/api/pay/bank-transfer")
async def pay_bank_transfer(req: BankTransferRequest):
    """Initiate a bank transfer payment via Flutterwave."""
    if not FLW_SECRET_KEY:
        raise HTTPException(503, "Flutterwave is not configured. Set FLW_SECRET_KEY.")

    tx_ref = f"KC-BANK-{uuid.uuid4().hex[:12]}"

    payload = {
        "tx_ref": tx_ref,
        "amount": req.amount,
        "currency": "ZMW",
        "redirect_url": f"{FRONTEND_URL}?payment=success&ref={tx_ref}",
        "customer": {
            "email": req.email,
            "name": req.fullname,
        },
        "customizations": {
            "title": "Kahyata's Consultancy Firm",
            "description": "Payment for tech accessories",
        },
        "payment_options": "banktransfer",
        "meta": {
            "source": "kahyata-portfolio",
            "bank_code": req.bank_code,
            "items": str(req.items) if req.items else "",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FLW_BASE}/payments",
            json=payload,
            headers={
                "Authorization": f"Bearer {FLW_SECRET_KEY}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"Flutterwave error: {resp.text}")

    data = resp.json()
    return {
        "status": "success",
        "gateway": "flutterwave",
        "tx_ref": tx_ref,
        "payment_link": data.get("data", {}).get("link", ""),
        "message": data.get("message", "Payment link created"),
    }


# ---------------------------------------------------------------------------
# Flutterwave Zambia Mobile Money (direct API – MTN & Zamtel)
# ---------------------------------------------------------------------------
@app.post("/api/pay/flw-mobile-money")
async def pay_flw_mobile_money(req: MobileMoneyRequest):
    """Initiate Zambia mobile money payment via Flutterwave (MTN/Zamtel)."""
    if not FLW_SECRET_KEY:
        raise HTTPException(503, "Flutterwave is not configured. Set FLW_SECRET_KEY.")

    tx_ref = f"KC-FMM-{uuid.uuid4().hex[:12]}"

    payload = {
        "phone_number": req.phone_number,
        "network": req.network,
        "amount": req.amount,
        "currency": "ZMW",
        "fullname": req.fullname,
        "email": req.email,
        "tx_ref": tx_ref,
        "redirect_url": f"{FRONTEND_URL}?payment=success&ref={tx_ref}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FLW_BASE}/charges?type=mobile_money_zambia",
            json=payload,
            headers={
                "Authorization": f"Bearer {FLW_SECRET_KEY}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"Flutterwave error: {resp.text}")

    data = resp.json()
    redirect_url = ""
    if data.get("meta", {}).get("authorization", {}).get("redirect"):
        redirect_url = data["meta"]["authorization"]["redirect"]

    return {
        "status": "success",
        "gateway": "flutterwave",
        "tx_ref": tx_ref,
        "redirect_url": redirect_url,
        "message": data.get("message", "Charge initiated"),
        "data": data.get("data", {}),
    }


# ---------------------------------------------------------------------------
# Verify Payment
# ---------------------------------------------------------------------------
@app.get("/api/pay/verify/{tx_ref}")
async def verify_payment(tx_ref: str, gateway: str = "flutterwave"):
    """Verify a payment by transaction reference."""
    if gateway == "moneyunify":
        if not MONEYUNIFY_AUTH_ID:
            raise HTTPException(503, "MoneyUnify not configured.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MU_BASE}/payments/verify",
                data={
                    "reference": tx_ref,
                    "auth_id": MONEYUNIFY_AUTH_ID,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
        if resp.status_code != 200:
            raise HTTPException(502, f"MoneyUnify verify error: {resp.text}")
        return resp.json()

    # Flutterwave verification
    if not FLW_SECRET_KEY:
        raise HTTPException(503, "Flutterwave not configured.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FLW_BASE}/transactions/verify_by_reference?tx_ref={tx_ref}",
            headers={"Authorization": f"Bearer {FLW_SECRET_KEY}"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Flutterwave verify error: {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------
@app.post("/api/webhooks/flutterwave")
async def flutterwave_webhook(request: Request):
    """Handle Flutterwave payment webhooks."""
    body = await request.json()
    # In production, verify the webhook signature using FLW_SECRET_HASH
    event = body.get("event", "")
    data = body.get("data", {})
    status = data.get("status", "")
    tx_ref = data.get("tx_ref", "")
    print(f"[Flutterwave Webhook] event={event} status={status} tx_ref={tx_ref}")
    return {"status": "ok"}


@app.post("/api/webhooks/moneyunify")
async def moneyunify_webhook(request: Request):
    """Handle MoneyUnify payment webhooks."""
    body = await request.json()
    print(f"[MoneyUnify Webhook] {body}")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Zambian Banks List
# ---------------------------------------------------------------------------
@app.get("/api/banks")
def list_banks():
    """Return list of supported Zambian banks."""
    return {"banks": ZAMBIAN_BANKS}


@app.get("/api/mobile-networks")
def list_networks():
    """Return list of supported mobile money networks."""
    return {"networks": MOBILE_NETWORKS}
