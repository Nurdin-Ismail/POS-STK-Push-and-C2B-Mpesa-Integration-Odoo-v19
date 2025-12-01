import json
import requests
import base64
from datetime import datetime, timedelta
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

# Token cache
_TOKEN_CACHE = {}

class MpesaController(http.Controller):

    def _get_api_url(self, company, endpoint):
        """Get API URL based on environment setting"""
        environment = company.mpesa_environment or 'sandbox'
        
        base_urls = {
            'sandbox': 'https://sandbox.safaricom.co.ke',
            'production': 'https://api.safaricom.co.ke'
        }
        
        endpoints = {
            'oauth': '/oauth/v1/generate?grant_type=client_credentials',
            'stk_push': '/mpesa/stkpush/v1/processrequest',
            'stk_query': '/mpesa/stkpushquery/v1/query',
            'c2b_register': '/mpesa/c2b/v1/registerurl'
        }
        
        base_url = base_urls.get(environment, base_urls['sandbox'])
        endpoint_path = endpoints.get(endpoint, '')
        
        return f"{base_url}{endpoint_path}"

    def _get_transaction_type(self, company):
        """Get transaction type based on account type setting"""
        account_type = company.mpesa_account_type or 'paybill'
        
        transaction_types = {
            'paybill': 'CustomerPayBillOnline',
            'till': 'CustomerBuyGoodsOnline'
        }
        
        return transaction_types.get(account_type, 'CustomerPayBillOnline')

    def _get_access_token(self, company, force_refresh=False):
        """Generate M-Pesa access token with caching"""
        try:
            cache_key = company.id
            
            # Check cached token (unless force refresh)
            if not force_refresh and cache_key in _TOKEN_CACHE:
                cached = _TOKEN_CACHE[cache_key]
                if cached['expires_at'] > datetime.now():
                    _logger.info("✓ Using cached M-Pesa access token")
                    return {'access_token': cached['token']}
                else:
                    _logger.info("⚠ Cached token expired, fetching new one")
            
            consumer_key = company.mpesa_consumer_key
            consumer_secret = company.mpesa_consumer_secret
            environment = company.mpesa_environment or 'sandbox'
            
            _logger.info("="*70)
            _logger.info("GETTING NEW M-PESA ACCESS TOKEN")
            _logger.info("="*70)
            _logger.info(f"Environment: {environment.upper()}")
            _logger.info(f"Force Refresh: {force_refresh}")
            
            if not consumer_key or not consumer_secret:
                _logger.error("❌ M-Pesa credentials not configured")
                return {'error': 'M-Pesa credentials not configured'}
            
            api_url = self._get_api_url(company, 'oauth')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(
                api_url,
                auth=(consumer_key, consumer_secret),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_in = int(token_data.get('expires_in', 3599))
                
                # Cache for 50 minutes (10 min buffer before 1hr expiry)
                _TOKEN_CACHE[cache_key] = {
                    'token': access_token,
                    'expires_at': datetime.now() + timedelta(seconds=expires_in - 600)
                }
                
                _logger.info(f"✓ New access token obtained (cached for {(expires_in - 600) / 60:.1f} minutes)")
                return {'access_token': access_token}
            else:
                _logger.error(f"❌ Token fetch failed (Status {response.status_code})")
                _logger.error(f"Response: {response.text[:500]}")
                
                # Fallback to cached token if WAF blocked and we have one
                if 'Incapsula' in response.text and cache_key in _TOKEN_CACHE:
                    _logger.warning("⚠ WAF block - using cached token as fallback")
                    cached = _TOKEN_CACHE[cache_key]
                    return {'access_token': cached['token']}
                
                return {'error': 'Failed to get access token'}
                
        except requests.exceptions.Timeout:
            _logger.error("❌ Token request timeout")
            if cache_key in _TOKEN_CACHE:
                _logger.warning("⚠ Timeout - using cached token as fallback")
                return {'access_token': _TOKEN_CACHE[cache_key]['token']}
            return {'error': 'Token request timeout'}
        except Exception as e:
            _logger.error(f"❌ Token exception: {str(e)}")
            return {'error': str(e)}

    def _make_mpesa_request(self, company, method, url, payload):
        """
        Make M-Pesa API request with automatic token refresh on 401
        Returns: (success, response_data)
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            # Get token (force refresh on retry)
            force_refresh = (attempt > 0)
            token_response = self._get_access_token(company, force_refresh=force_refresh)
            
            if 'error' in token_response:
                _logger.error(f"❌ Token error on attempt {attempt + 1}: {token_response['error']}")
                if attempt == max_retries - 1:
                    return False, {'error': token_response['error']}
                continue
            
            access_token = token_response.get('access_token')
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }
            
            try:
                if method == 'POST':
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                else:
                    response = requests.get(url, headers=headers, timeout=30)
                
                response_data = response.json()
                
                # Check for auth errors
                if response.status_code == 401 or response_data.get('errorCode') == '403.011.01':
                    _logger.warning(f"⚠ Auth error on attempt {attempt + 1} - token may be invalid")
                    # Clear cache and retry
                    if company.id in _TOKEN_CACHE:
                        del _TOKEN_CACHE[company.id]
                        _logger.info("🔄 Cleared token cache, will retry with fresh token")
                    if attempt < max_retries - 1:
                        continue
                
                # Success or non-auth error
                return True, response_data
                
            except requests.exceptions.Timeout:
                _logger.error(f"❌ Request timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    return False, {'error': 'Request timeout'}
            except Exception as e:
                _logger.error(f"❌ Request exception on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    return False, {'error': str(e)}
        
        return False, {'error': 'Max retries exceeded'}

    @http.route('/mpesa/stk_push', type='json', auth='user', methods=['POST'])
    def initiate_stk_push(self, phone_number, amount, order_reference):
        """Initiate M-Pesa STK Push"""
        _logger.info("="*70)
        _logger.info("INITIATING M-PESA STK PUSH")
        _logger.info("="*70)
        _logger.info(f"Phone: {phone_number}, Amount: {amount}, Ref: {order_reference}")
        
        try:
            company = request.env.company
            shortcode = company.mpesa_shortcode
            passkey = company.mpesa_passkey
            environment = company.mpesa_environment or 'sandbox'
            account_type = company.mpesa_account_type or 'paybill'
            
            _logger.info(f"Environment: {environment.upper()}")
            _logger.info(f"Account Type: {account_type.upper()}")
            
            if not shortcode or not passkey:
                return {'success': False, 'message': 'M-Pesa not configured'}
            
            # Format phone
            phone = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            elif not phone.startswith('254'):
                phone = '254' + phone
            
            # Format amount
            try:
                amount_int = max(1, int(round(float(amount))))
            except (ValueError, TypeError):
                return {'success': False, 'message': f'Invalid amount: {amount}'}
            
            # Generate password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_str = f"{shortcode}{passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode('utf-8')
            
            # Get API URL based on environment
            api_url = self._get_api_url(company, 'stk_push')
            callback_url = f"{request.httprequest.host_url}mpesa/callback"
            
            # Get transaction type based on account type
            transaction_type = self._get_transaction_type(company)
            
            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": transaction_type,
                "Amount": amount_int,
                "PartyA": phone,
                "PartyB": shortcode,
                "PhoneNumber": phone,
                "CallBackURL": "https://mydomain.com/pat",
                "AccountReference": order_reference,
                "TransactionDesc": f"Payment for {order_reference}"
            }
            
            _logger.info(f"API URL: {api_url}")
            _logger.info(f"Transaction Type: {transaction_type}")
            _logger.info(f"Callback URL: {callback_url}")
            _logger.info(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Make request with auto-retry
            success, response_data = self._make_mpesa_request(company, 'POST', api_url, payload)
            
            _logger.info(f"Response: {json.dumps(response_data, indent=2)}")
            
            if success and response_data.get('ResponseCode') == '0':
                _logger.info("✓ STK Push sent successfully")
                return {
                    'success': True,
                    'message': 'STK Push sent successfully',
                    'checkout_request_id': response_data.get('CheckoutRequestID'),
                    'merchant_request_id': response_data.get('MerchantRequestID')
                }
            else:
                error_msg = response_data.get('errorMessage') or response_data.get('error') or 'STK Push failed'
                _logger.error(f"❌ STK Push failed: {error_msg}")
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            _logger.error(f"❌ Exception: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Error: {str(e)}'}

    @http.route('/mpesa/callback', type='json', auth='public', methods=['POST'], csrf=False)
    def mpesa_callback(self):
        """
        Smart callback handler - automatically detects and processes both:
        - STK Push callbacks (from /mpesa/stk_push)
        - C2B callbacks (from customer direct payments)
        """
        try:
            data = json.loads(request.httprequest.data)
            _logger.info("="*70)
            _logger.info("M-PESA CALLBACK RECEIVED")
            _logger.info("="*70)
            _logger.info(json.dumps(data, indent=2))
            
            # Detect callback type by structure
            if 'Body' in data and 'stkCallback' in data.get('Body', {}):
                # STK Push callback
                _logger.info("📱 Detected: STK Push Callback")
                return self._handle_stk_callback(data)
            elif 'TransID' in data:
                # C2B callback
                _logger.info("💰 Detected: C2B Direct Payment Callback")
                return self._handle_c2b_callback(data)
            else:
                _logger.warning("⚠ Unknown callback format")
                _logger.warning(f"Data keys: {list(data.keys())}")
                return {'ResultCode': 1, 'ResultDesc': 'Unknown callback format'}
                
        except Exception as e:
            _logger.error(f"❌ Callback error: {str(e)}", exc_info=True)
            return {'ResultCode': 1, 'ResultDesc': 'Failed'}

    def _handle_stk_callback(self, data):
        """Handle STK Push callback"""
        try:
            stk_callback = data.get('Body', {}).get('stkCallback', {})
            
            merchant_request_id = stk_callback.get('MerchantRequestID')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = str(stk_callback.get('ResultCode', ''))
            result_desc = stk_callback.get('ResultDesc', '')
            
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            amount = mpesa_receipt = transaction_date = phone_number = None
            
            for item in items:
                name = item.get('Name', '')
                value = item.get('Value', '')
                if name == 'Amount':
                    amount = float(value)
                elif name == 'MpesaReceiptNumber':
                    mpesa_receipt = str(value)
                elif name == 'TransactionDate':
                    transaction_date = str(value)
                elif name == 'PhoneNumber':
                    phone_number = str(value)
            
            request.env['mpesa.callback.entry'].sudo().create({
                'callback_type': 'stk',
                'merchant_request_id': merchant_request_id,
                'checkout_request_id': checkout_request_id,
                'result_code': result_code,
                'result_desc': result_desc,
                'amount': amount or 0,
                'mpesa_receipt_number': mpesa_receipt,
                'transaction_date': transaction_date,
                'phone_number': phone_number,
                'raw_callback_data': json.dumps(data, indent=2)
            })
            
            _logger.info(f"✓ STK callback entry created for {checkout_request_id}")
            return {'ResultCode': 0, 'ResultDesc': 'Accepted'}
            
        except Exception as e:
            _logger.error(f"❌ STK callback processing error: {str(e)}", exc_info=True)
            return {'ResultCode': 1, 'ResultDesc': 'Failed'}

    def _handle_c2b_callback(self, data):
        """Handle C2B (Customer to Business) callback"""
        try:
            # Extract C2B data
            transaction_type = data.get('TransactionType', '')
            trans_id = data.get('TransID', '')
            trans_time = data.get('TransTime', '')
            trans_amount = float(data.get('TransAmount', 0))
            business_short_code = data.get('BusinessShortCode', '')
            bill_ref_number = data.get('BillRefNumber', '')
            msisdn = data.get('MSISDN', '')
            first_name = data.get('FirstName', '')
            middle_name = data.get('MiddleName', '')
            last_name = data.get('LastName', '')
            
            # Combine customer name
            name_parts = [first_name, middle_name, last_name]
            customer_name = ' '.join([part for part in name_parts if part]).strip()
            
            request.env['mpesa.callback.entry'].sudo().create({
                'callback_type': 'c2b',
                'trans_id': trans_id,
                'transaction_type': transaction_type,
                'transaction_date': trans_time,
                'amount': trans_amount,
                'mpesa_receipt_number': trans_id,  # C2B uses TransID as receipt
                'phone_number': msisdn,
                'customer_name': customer_name,
                'bill_ref_number': bill_ref_number,
                'raw_callback_data': json.dumps(data, indent=2)
            })
            
            _logger.info(f"✓ C2B callback entry created for TransID: {trans_id}")
            return {'ResultCode': 0, 'ResultDesc': 'Accepted'}
            
        except Exception as e:
            _logger.error(f"❌ C2B callback processing error: {str(e)}", exc_info=True)
            return {'ResultCode': 1, 'ResultDesc': 'Failed'}

    @http.route('/mpesa/check_status', type='json', auth='user', methods=['POST'])
    def check_payment_status(self, checkout_request_id):
        """Check STK Push payment status"""
        _logger.info(f"Checking status for: {checkout_request_id}")
        
        try:
            company = request.env.company
            shortcode = company.mpesa_shortcode
            passkey = company.mpesa_passkey
            environment = company.mpesa_environment or 'sandbox'
            
            _logger.info(f"Environment: {environment.upper()}")
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_str = f"{shortcode}{passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode('utf-8')
            
            api_url = self._get_api_url(company, 'stk_query')
            
            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            _logger.info(f"Query URL: {api_url}")
            
            success, response_data = self._make_mpesa_request(company, 'POST', api_url, payload)
            
            _logger.info(f"Status: {json.dumps(response_data, indent=2)}")
            
            if not success:
                return {'success': False, 'status': 'error', 'message': response_data.get('error', 'Status check failed')}
            
            # Check for rate limit fault
            if 'fault' in response_data:
                fault_string = response_data.get('fault', {}).get('faultstring', '')
                if 'rate' in fault_string.lower() or 'spike arrest' in fault_string.lower():
                    _logger.warning(f"⚠ Rate limit hit: {fault_string}")
                    return {'success': False, 'status': 'error', 'message': 'Rate limit - will retry'}
                else:
                    return {'success': False, 'status': 'error', 'message': fault_string}
            
            result_code = str(response_data.get('ResultCode', ''))
            result_desc = response_data.get('ResultDesc', 'Unknown error')
            
            # Success
            if result_code == '0':
                return {'success': True, 'status': 'completed', 'message': 'Payment completed successfully'}
            
            # User cancellation/timeout scenarios
            elif result_code == '1032':
                # User canceled or STK prompt timed out (1-3 minutes)
                return {'success': False, 'status': 'cancelled', 'message': 'Payment cancelled by user'}
            
            elif result_code == '1037':
                # No response from user OR user unreachable (SIM/network issues)
                return {'success': False, 'status': 'cancelled', 'message': 'Request timed out - customer did not respond'}
            
            # Insufficient funds
            elif result_code == '1':
                return {'success': False, 'status': 'failed', 'message': 'Insufficient balance'}
            
            # Still processing
            elif result_code == '4999':
                return {'success': True, 'status': 'pending', 'message': 'Transaction still processing'}
            
            # Transaction in progress for subscriber
            elif result_code == '1001':
                return {'success': False, 'status': 'error', 'message': 'Transaction already in progress for this number'}
            
            # Invalid initiator/wrong PIN
            elif result_code == '2001':
                return {'success': False, 'status': 'failed', 'message': 'Invalid PIN entered'}
            
            # Transaction expired
            elif result_code == '1019':
                return {'success': False, 'status': 'failed', 'message': 'Transaction expired'}
            
            # Push request error
            elif result_code in ['1025', '9999']:
                return {'success': False, 'status': 'error', 'message': 'System error - please retry'}
            
            # Default pending if ResponseCode is 0
            elif response_data.get('ResponseCode') == '0':
                return {'success': True, 'status': 'pending', 'message': 'Payment pending'}
            
            # Unknown error
            else:
                _logger.warning(f"⚠ Unhandled result code: {result_code} - {result_desc}")
                return {'success': False, 'status': 'failed', 'message': result_desc}
                
        except Exception as e:
            _logger.error(f"❌ Status check exception: {str(e)}", exc_info=True)
            return {'success': False, 'status': 'error', 'message': str(e)}

    @http.route('/mpesa/register_c2b_urls', type='json', auth='user', methods=['POST'])
    def register_c2b_urls(self):
        """
        Register C2B validation and confirmation URLs with Safaricom
        This only needs to be done once per shortcode
        """
        _logger.info("="*70)
        _logger.info("REGISTERING C2B URLs WITH SAFARICOM")
        _logger.info("="*70)
        
        try:
            company = request.env.company
            shortcode = company.mpesa_shortcode
            environment = company.mpesa_environment or 'sandbox'
            
            _logger.info(f"Environment: {environment.upper()}")
            
            if not shortcode:
                return {'success': False, 'message': 'M-Pesa shortcode not configured'}
            
            # Get API URL based on environment
            api_url = self._get_api_url(company, 'c2b_register')
            callback_url = f"{request.httprequest.host_url}mpesa/callback"
            
            payload = {
                "ShortCode": shortcode,
                "ResponseType": "Completed",
                "ConfirmationURL": callback_url,
                "ValidationURL": callback_url
            }
            
            _logger.info(f"Register URL: {api_url}")
            _logger.info(f"Confirmation URL: {callback_url}")
            _logger.info(f"Validation URL: {callback_url}")
            
            # Make request with auto-retry
            success, response_data = self._make_mpesa_request(company, 'POST', api_url, payload)
            
            _logger.info(f"Response: {json.dumps(response_data, indent=2)}")
            
            if success and response_data.get('ResponseCode') == '0':
                _logger.info("✓ C2B URLs registered successfully")
                return {
                    'success': True,
                    'message': 'C2B URLs registered successfully',
                    'response': response_data
                }
            else:
                error_msg = response_data.get('errorMessage') or response_data.get('error') or 'Registration failed'
                _logger.error(f"❌ C2B URL registration failed: {error_msg}")
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            _logger.error(f"❌ Registration exception: {str(e)}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route('/mpesa/search_unreconciled_callbacks', type='json', auth='user', methods=['POST'])
    def search_unreconciled_callbacks(self, amount, max_age_minutes=10):
        """
        Search for unreconciled C2B callbacks matching the given amount
        within the specified time window (default: last 10 minutes)
        """
        _logger.info("="*70)
        _logger.info("SEARCHING UNRECONCILED C2B CALLBACKS")
        _logger.info("="*70)
        _logger.info(f"Amount: {amount}, Max Age: {max_age_minutes} minutes")
        
        try:
            # Calculate time threshold
            time_threshold = datetime.now() - timedelta(minutes=max_age_minutes)
            
            # Search for matching callbacks
            callbacks = request.env['mpesa.callback.entry'].sudo().search([
                ('callback_type', '=', 'c2b'),
                ('status', '=', 'success'),
                ('is_reconciled', '=', False),
                ('amount', '=', float(amount)),
                ('create_date', '>=', time_threshold)
            ], order='create_date desc')
            
            _logger.info(f"✓ Found {len(callbacks)} matching callbacks")
            
            # Format results
            results = []
            for callback in callbacks:
                results.append({
                    'id': callback.id,
                    'trans_id': callback.trans_id,
                    'mpesa_receipt_number': callback.mpesa_receipt_number,
                    'phone_number': callback.phone_number,
                    'customer_name': callback.customer_name or 'Unknown',
                    'amount': callback.amount,
                    'transaction_date': callback.transaction_date,
                    'create_date': callback.create_date.strftime('%Y-%m-%d %H:%M:%S') if callback.create_date else '',
                    'bill_ref_number': callback.bill_ref_number or ''
                })
            
            return {
                'success': True,
                'callbacks': results,
                'count': len(results)
            }
            
        except Exception as e:
            _logger.error(f"❌ Search error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': str(e),
                'callbacks': [],
                'count': 0
            }

    @http.route('/mpesa/reconcile_callback', type='json', auth='user', methods=['POST'])
    def reconcile_callback(self, callback_id, order_id):
        """Link callback to POS order and payment"""
        _logger.info("="*70)
        _logger.info("RECONCILING CALLBACK")
        _logger.info("="*70)
        _logger.info(f"Callback ID: {callback_id}, Order ID: {order_id}")
        
        try:
            callback = request.env['mpesa.callback.entry'].sudo().browse(callback_id)
            
            if not callback.exists():
                _logger.error(f"❌ Callback {callback_id} not found")
                return {'success': False, 'message': 'Callback not found'}
            
            if callback.is_reconciled:
                _logger.warning(f"⚠ Callback {callback_id} already reconciled")
                return {'success': False, 'message': 'Callback already reconciled'}
            
            # Find the order
            order = request.env['pos.order'].sudo().browse(order_id)
            if not order.exists():
                _logger.error(f"❌ Order {order_id} not found")
                return {'success': False, 'message': 'Order not found'}
            
            # Find M-Pesa payment in order
            mpesa_payment = order.payment_ids.filtered(
                lambda p: 'mpesa' in p.payment_method_id.name.lower()
            )
            
            if mpesa_payment:
                # Prepare M-Pesa details based on callback type
                payment_vals = {
                    'mpesa_receipt_number': callback.mpesa_receipt_number,
                    'mpesa_phone_number': callback.phone_number,
                    'mpesa_transaction_date': callback.transaction_date,
                    'mpesa_callback_id': callback.id,
                }
                
                # Add customer name only for C2B (STK doesn't have this field)
                if callback.callback_type == 'c2b' and callback.customer_name:
                    payment_vals['mpesa_customer_name'] = callback.customer_name
                
                mpesa_payment.write(payment_vals)
                _logger.info(f"✓ M-Pesa payment updated with {callback.callback_type.upper()} callback details")
            else:
                _logger.warning("⚠ No M-Pesa payment found in order to update")
            
            # Update callback
            callback.write({
                'is_reconciled': True,
                'pos_order_id': order_id,
                'reconciled_date': datetime.now()
            })
            
            _logger.info(f"✓ {callback.callback_type.upper()} callback reconciled to order {order_id}")
            _logger.info(f"  Receipt: {callback.mpesa_receipt_number}")
            _logger.info(f"  Amount: {callback.amount}")
            if callback.callback_type == 'c2b':
                _logger.info(f"  Customer: {callback.customer_name}")
            
            return {
                'success': True,
                'message': 'Callback reconciled successfully',
                'receipt_number': callback.mpesa_receipt_number
            }
            
        except Exception as e:
            _logger.error(f"❌ Reconcile error: {str(e)}", exc_info=True)
            return {'success': False, 'message': str(e)}
        

    @http.route('/mpesa/check_callback_received', type='json', auth='user', methods=['POST'])
    def check_callback_received(self, checkout_request_id):
        """
        Check if STK callback already received for this checkout request
        Returns callback data if found, otherwise returns callback_received: False
        """
        try:
            callback = request.env['mpesa.callback.entry'].sudo().search([
                ('callback_type', '=', 'stk'),
                ('checkout_request_id', '=', checkout_request_id)
            ], limit=1, order='create_date desc')
            
            if callback:
                _logger.info(f"✓ Callback found for {checkout_request_id}")
                _logger.info(f"  Status: {callback.status}")
                _logger.info(f"  Receipt: {callback.mpesa_receipt_number}")
                
                return {
                    'callback_received': True,
                    'callback_id': callback.id,  # ADD THIS
                    'status': callback.status,
                    'receipt_number': callback.mpesa_receipt_number,
                    'result_desc': callback.result_desc,
                    'amount': callback.amount
                }
            else:
                return {'callback_received': False}
                
        except Exception as e:
            _logger.error(f"❌ Check callback error: {str(e)}", exc_info=True)
            return {'callback_received': False}