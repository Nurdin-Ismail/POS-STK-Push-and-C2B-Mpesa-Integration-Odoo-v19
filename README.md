# M-Pesa Integration for Odoo POS

A comprehensive M-Pesa payment integration module for Odoo 19 Point of Sale, supporting both STK Push (Lipa Na M-Pesa) and C2B (Customer to Business) direct payments with intelligent callback reconciliation.

![Version](https://img.shields.io/badge/version-1.0-blue)
![Odoo](https://img.shields.io/badge/odoo-19.0-purple)
![License](https://img.shields.io/badge/license-LGPL--3-green)

---

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Usage](#usage)
  - [STK Push Flow](#stk-push-flow)
  - [C2B Direct Payment Flow](#c2b-direct-payment-flow)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)

---

## ✨ Features

### 🔐 Dual Payment Modes

- **STK Push (Lipa Na M-Pesa Online)**: Initiate payments directly from POS with phone number entry
- **C2B Direct Payments**: Handle customer-initiated payments with intelligent matching

### 🌍 Multi-Environment Support

- **Sandbox Mode**: Test with Safaricom sandbox credentials
- **Production Mode**: Live transactions with production credentials
- Easy switching between environments via UI settings

### 🏪 Account Type Flexibility

- **Paybill Accounts**: Standard business paybill numbers
- **Till Numbers**: Buy Goods/Services till numbers
- Automatic transaction type handling based on account configuration

### 🔄 Smart Callback Handling

- Automatic detection of STK and C2B callbacks
- Intelligent payment matching by amount and timestamp
- Prevents duplicate reconciliation
- 10-minute time window for recent payments

### 💼 POS Integration

- Toggle between STK Push and C2B modes
- Real-time payment status checking
- User-friendly payment selection interface
- Validation with or without payment matching

### 📊 Comprehensive Tracking

- All M-Pesa transactions logged
- Receipt number tracking
- Customer information capture
- Order reconciliation history
- Detailed callback data storage

### 🎨 User Experience

- Beautiful payment selection popup
- Real-time status notifications
- Error handling with clear messages
- Phone number validation
- Amount verification

---

## 📦 Prerequisites

### Odoo Requirements

- Odoo 19.0 or higher
- Point of Sale module installed
- Python 3.10+

### M-Pesa Requirements

- Active Safaricom M-Pesa account (Paybill or Till)
- Daraja API credentials (Consumer Key & Secret)
- Lipa Na M-Pesa Online Passkey (for STK Push)
- Publicly accessible server with HTTPS (for callbacks)




## ⚙️ Configuration

### Step 1: M-Pesa Settings

Navigate to: **Settings → M-Pesa Integration**

#### Environment Configuration

```
Environment: Sandbox (for testing) or Production (for live)
Account Type: Paybill or Buy Goods (Till Number)
```

#### API Credentials

Get these from [Safaricom Developer Portal](https://developer.safaricom.co.ke):

```
Consumer Key: Your app consumer key
Consumer Secret: Your app consumer secret
Business Shortcode: Your paybill/till number
Lipa Na M-Pesa Passkey: Your STK Push passkey
```

#### Test Connection

Click **"Test Connection"** to verify credentials work.

### Step 2: Register C2B Callbacks

For direct customer payments, register your callback URL:

1. Ensure your server is publicly accessible (not localhost)
2. Click **"Register C2B Callback URLs"**
3. Confirm successful registration
4. Your callback URL: `https://yourdomain.com/mpesa/callback`

### Step 3: Payment Method Setup

Navigate to: **Point of Sale → Configuration → Payment Methods**

1. Create new payment method
2. Name: "M-Pesa" (must contain "mpesa")
3. Journal: Create M-Pesa journal
4. Save

---

## 💡 Usage

### STK Push Flow

**Use Case**: Clerk initiates payment request to customer's phone

1. **Start Order**
   - Add products to cart
   - Click "Payment"

2. **Select M-Pesa**
   - Click M-Pesa payment method
   - **Turn toggle ON** (STK Push enabled)

3. **Initiate Payment**
   - Click "Validate"
   - Enter customer phone number (07XXXXXXXX or 01XXXXXXXX)
   - Confirm

4. **Customer Action**
   - Customer receives M-Pesa prompt on phone
   - Customer enters PIN
   - Confirms payment

5. **Completion**
   - System checks payment status automatically
   - Shows success/failure notification
   - Order validates on successful payment

**Status Messages:**
- ✅ "Payment successful!" → Order completed
- ❌ "Payment cancelled" → User cancelled on phone
- ❌ "Insufficient balance" → Not enough funds
- ⏱️ "Payment timeout" → No response after 75 seconds

---

### C2B Direct Payment Flow

**Use Case**: Customer pays directly via M-Pesa app before clerk processes order

1. **Customer Payment**
   - Customer sends M-Pesa payment to your shortcode
   - Payment captured in system automatically

2. **Start Order**
   - Add products to cart
   - Click "Payment"

3. **Select M-Pesa**
   - Click M-Pesa payment method for exact amount
   - **Keep toggle OFF** (C2B mode)

4. **Validate**
   - Click "Validate"
   - System searches for matching payments (last 10 minutes)

5. **Payment Selection**
   
   **Scenario A: Payment(s) Found**
   - Popup shows matching payments with:
     - Customer name
     - Phone number
     - Receipt number
     - Transaction date/time
   - Select correct payment
   - Confirm
   - Order validates and payment is linked

   **Scenario B: No Payment Found**
   - System shows "No M-Pesa Payment Found"
   - Options:
     - Cancel → Try again or check amount
     - Validate Anyway → Process without matching

6. **Skip Matching**
   - Click "Validate Without Matching Payment"
   - Useful when payment not yet reflected in system

**Important Notes:**
- ✅ Only shows unreconciled payments
- ✅ Only shows successful transactions
- ✅ Exact amount matching
- ✅ 10-minute time window
- ✅ Prevents duplicate matching

---

## 🧪 Testing

### Test Environment Setup

1. **Get Sandbox Credentials**
   - Register at [Safaricom Developer Portal](https://developer.safaricom.co.ke)
   - Create test app
   - Get sandbox credentials

2. **Configure Sandbox**
   ```
   Environment: Sandbox
   Consumer Key: [sandbox key]
   Consumer Secret: [sandbox secret]
   Shortcode: 174379 (or your test shortcode)
   Passkey: [sandbox passkey]
   ```

3. **Test Connection**
   - Click "Test Connection"
   - Should show success

### Testing STK Push

1. Use test phone number: **254708374149**
2. Amount: Any amount (e.g., KES 100)
3. On phone prompt, enter PIN: **1234**
4. Payment should complete successfully

### Testing C2B Callbacks

Use Postman or any HTTP client:

**Endpoint:** `POST https://yourdomain.com/mpesa/callback`

**Headers:**
```json
{
  "Content-Type": "application/json"
}
```

**Body (C2B Payment):**
```json
{
  "TransactionType": "Pay Bill",
  "TransID": "TEST123ABC",
  "TransTime": "20231113150100",
  "TransAmount": "100.00",
  "BusinessShortCode": "600638",
  "BillRefNumber": "ORDER-001",
  "MSISDN": "254712345678",
  "FirstName": "John",
  "MiddleName": "",
  "LastName": "Doe"
}
```

**Expected Response:**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

**Verification:**
1. Go to: **Accounting → M-Pesa Callbacks**
2. Should see new entry
3. Type: C2B
4. Status: Success
5. Is Reconciled: False

### Testing C2B Matching in POS

1. Send test callback (above)
2. In POS:
   - Add product worth KES 100
   - Add M-Pesa payment
   - Keep toggle OFF
   - Click Validate
3. Popup should show the payment
4. Select it
5. Order should validate
6. Callback should be marked as reconciled

---

## 🔧 Troubleshooting

### STK Push Issues

**Problem: "M-Pesa not configured"**
- ✅ Check credentials in Settings
- ✅ Ensure Consumer Key, Secret, Shortcode, Passkey all filled
- ✅ Click "Test Connection"

**Problem: "Invalid phone number"**
- ✅ Format: 07XXXXXXXX or 01XXXXXXXX
- ✅ Must be valid Kenyan number
- ✅ Remove spaces, dashes, brackets

**Problem: "Payment timeout"**
- Customer didn't enter PIN in time
- Network issues
- User can try again

**Problem: STK not reaching phone**
- ✅ Check phone has network
- ✅ Verify phone number is correct
- ✅ Check Safaricom M-Pesa service status
- ✅ Ensure passkey is correct

### C2B Issues

**Problem: "No M-Pesa Payment Found"**
- ✅ Check amount matches exactly
- ✅ Payment must be within last 10 minutes
- ✅ Verify callback was received: Accounting → M-Pesa Callbacks
- ✅ Check payment status is "Success"
- ✅ Ensure payment not already reconciled

**Problem: Callbacks not received**
- ✅ Register C2B URLs: Settings → Register C2B Callback URLs
- ✅ Ensure server is publicly accessible (not localhost)
- ✅ Verify callback URL is correct
- ✅ Check Odoo logs for callback attempts

**Problem: Wrong payment selected**
- Cannot undo - payment already reconciled
- Contact admin to manually update database
- Prevention: Carefully verify customer details before selecting

### General Issues

**Problem: Environment mismatch**
- ✅ Sandbox credentials don't work in Production
- ✅ Production credentials don't work in Sandbox
- ✅ Match environment setting with credentials

**Problem: API errors**
- Check Odoo logs: `tail -f /var/log/odoo/odoo.log`
- Look for M-Pesa related errors
- Check Safaricom API status

**Problem: Toggle not working**
- ✅ Refresh POS
- ✅ Clear browser cache
- ✅ Check JS console for errors

---

## 🏗️ Technical Architecture

### Backend Components

#### Controllers (`controllers/mpesa_controller.py`)

**Endpoints:**
- `/mpesa/stk_push` - Initiate STK Push
- `/mpesa/callback` - Receive M-Pesa callbacks (STK & C2B)
- `/mpesa/check_status` - Poll payment status
- `/mpesa/register_c2b_urls` - Register callback URLs
- `/mpesa/search_unreconciled_callbacks` - Search for matching payments
- `/mpesa/reconcile_callback` - Link payment to order

**Features:**
- Environment-aware API URLs
- Account type handling
- Token caching (50 min)
- Auto-retry on auth errors
- Comprehensive logging


## 📡 API Endpoints

### 1. STK Push

**POST** `/mpesa/stk_push`

**Auth:** User session required

**Request:**
```json
{
  "phone_number": "0712345678",
  "amount": 100,
  "order_reference": "ORDER-001"
}
```

**Response:**
```json
{
  "success": true,
  "message": "STK Push sent successfully",
  "checkout_request_id": "ws_CO_xxx",
  "merchant_request_id": "29115-xxx"
}
```

### 2. Check Status

**POST** `/mpesa/check_status`

**Auth:** User session required

**Request:**
```json
{
  "checkout_request_id": "ws_CO_xxx"
}
```

**Response:**
```json
{
  "success": true,
  "status": "completed",
  "message": "Payment completed"
}
```

**Status Values:**
- `completed` - Payment successful
- `pending` - Awaiting user action
- `cancelled` - User cancelled
- `failed` - Payment failed
- `error` - System error

### 3. M-Pesa Callback

**POST** `/mpesa/callback`

**Auth:** Public (no auth)

**STK Callback:**
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "xxx",
      "CheckoutRequestID": "ws_CO_xxx",
      "ResultCode": 0,
      "ResultDesc": "Success",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 100},
          {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
          {"Name": "TransactionDate", "Value": 20191219102115},
          {"Name": "PhoneNumber", "Value": 254708374149}
        ]
      }
    }
  }
}
```

**C2B Callback:**
```json
{
  "TransactionType": "Pay Bill",
  "TransID": "ABC123",
  "TransTime": "20191122063845",
  "TransAmount": "100.00",
  "BusinessShortCode": "600638",
  "BillRefNumber": "ORDER-001",
  "MSISDN": "254708374149",
  "FirstName": "John",
  "LastName": "Doe"
}
```

**Response:**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

### 4. Register C2B URLs

**POST** `/mpesa/register_c2b_urls`

**Auth:** User session required

**Response:**
```json
{
  "success": true,
  "message": "C2B URLs registered successfully"
}
```

### 5. Search Callbacks

**POST** `/mpesa/search_unreconciled_callbacks`

**Auth:** User session required

**Request:**
```json
{
  "amount": 100,
  "max_age_minutes": 10
}
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "callbacks": [
    {
      "id": 1,
      "trans_id": "ABC123",
      "mpesa_receipt_number": "ABC123",
      "phone_number": "254712345678",
      "customer_name": "John Doe",
      "amount": 100.0,
      "transaction_date": "20231113150100",
      "create_date": "2023-11-13 15:01:00"
    }
  ]
}
```

### 6. Reconcile Callback

**POST** `/mpesa/reconcile_callback`

**Auth:** User session required

**Request:**
```json
{
  "callback_id": 1,
  "order_id": 123
}
```

**Response:**
```json
{
  "success": true,
  "message": "Callback reconciled successfully",
  "receipt_number": "ABC123"
}
```

---



## 🚦 Production Deployment

### Pre-Deployment Checklist

- [ ] Test thoroughly in sandbox environment
- [ ] Obtain production credentials from Safaricom
- [ ] Verify server has public HTTPS URL
- [ ] Configure firewall to allow Safaricom IPs
- [ ] Set up SSL certificate
- [ ] Configure proper backup strategy
- [ ] Test callback reception
- [ ] Train staff on both payment flows

### Production Configuration

1. **Switch to Production**
   ```
   Settings → M-Pesa Integration
   Environment: Production
   ```

2. **Update Credentials**
   ```
   Consumer Key: [production key]
   Consumer Secret: [production secret]
   Shortcode: [live shortcode]
   Passkey: [production passkey]
   ```

3. **Test Connection**
   - Click "Test Connection"
   - Must succeed before going live

4. **Register Production Callbacks**
   - Click "Register C2B Callback URLs"
   - Verify registration success

5. **Process Test Transaction**
   - Use small amount (KES 10)
   - Test both STK and C2B flows
   - Verify reconciliation works

