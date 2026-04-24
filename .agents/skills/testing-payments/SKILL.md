# Testing: Kahyata Payment Integration

## Overview
The site has a checkout modal with 3 payment methods: Mobile Money (MTN/Airtel/Zamtel), Bank Transfer (12 Zambian banks), and Card (Visa/Mastercard). It supports a **demo mode** that works without API keys.

## Environments
- **Frontend:** Deployed to devinapps.com (static HTML)
- **Backend:** Deployed to Fly.io (FastAPI)
- The frontend is a single `index.html` file with inline CSS/JS

## Demo Mode vs Real Mode
- Demo mode activates when `window.KC_API_BASE` is falsy (empty string)
- In demo mode, `processPayment()` calls `showCheckoutSuccess('KC-DEMO-' + timestamp)` directly without API calls
- Real mode requires backend env vars: `FLW_SECRET_KEY`, `FLW_PUBLIC_KEY`, `MONEYUNIFY_AUTH_ID`

## Devin Secrets Needed
- None for demo mode testing
- For real payment testing: `FLW_SECRET_KEY`, `FLW_PUBLIC_KEY`, `MONEYUNIFY_AUTH_ID` (Flutterwave + MoneyUnify API keys)

## How to Test the Checkout Flow

### Prerequisites
1. Navigate to the Shop page
2. Add at least one product to cart (e.g., "TurboCharge 65W GaN" at K34.99)
3. Open cart drawer and click "Proceed to Checkout"

### Key Test Areas

#### Form Validation
- Empty name → toast "Please enter your name"
- Invalid email (no @) → toast "Please enter a valid email"
- Short phone (<10 digits) → toast "Please enter a valid phone number"
- No bank selected (bank tab) → toast "Please select a bank"
- Validation runs in order: name → email → method-specific fields

#### Payment Tabs
- **Mobile Money** (default): Shows 3 network selector cards (MTN MoMo, Airtel Money, Zamtel Kwacha) + phone input. Pay button: "Pay K{amount}"
- **Bank Transfer**: Shows dropdown with 12 Zambian banks. Pay button: "Pay via Bank K{amount}"
- **Card**: Shows Flutterwave redirect message. Pay button: "Pay with Card K{amount}"

#### Network Selector
- Clicking a network card sets `selectedNetwork` variable and toggles `.selected` CSS class
- Only one network can be selected at a time
- Default is MTN MoMo

#### Demo Payment Success
- Fill valid name, email, phone (10+ digits), select network
- Click Pay → success screen shows:
  - 🎉 emoji, "Payment Initiated!" heading
  - Context message about phone prompt
  - Reference starting with "KC-DEMO-"
  - "Continue Shopping" button
- Cart is cleared (localStorage `kc_cart` = `[]`, badge shows 0)

### Backend API Verification
- `GET /` → `{"status":"ok","service":"Kahyata Payments API"}`
- `GET /api/config` → JSON with `banks` (12 entries), `mobile_networks` (3: MTN, AIRTEL, ZAMTEL), `currency` = "ZMW"

## Tips & Gotchas
- The checkout modal is an overlay (`#checkout-overlay`). Use `openCheckout()` via console if the UI click path is blocked.
- When switching tabs, form field values (name/email) persist but devinid mappings may shift. Use console to set field values directly if needed: `document.getElementById('co-name').value = 'Test User'`
- The pay button might be offscreen in the modal. Scroll within the modal or call `processPayment()` via console as a fallback.
- Toast notifications appear at the top of the page and auto-dismiss. Capture them quickly in screenshots or check the DOM for the toast element.
- The SPA uses hash-based navigation. All pages are in one `index.html` file.
