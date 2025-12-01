from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Environment & Account Type
    mpesa_environment = fields.Selection(
        string="M-Pesa Environment",
        related="company_id.mpesa_environment",
        readonly=False
    )
    mpesa_account_type = fields.Selection(
        string="Account Type",
        related="company_id.mpesa_account_type",
        readonly=False
    )
    
    # Credentials
    mpesa_consumer_key = fields.Char(
        string="Consumer Key",
        related="company_id.mpesa_consumer_key",
        readonly=False
    )
    mpesa_consumer_secret = fields.Char(
        string="Consumer Secret",
        related="company_id.mpesa_consumer_secret",
        readonly=False
    )
    mpesa_passkey = fields.Char(
        string="Lipa Na M-Pesa Passkey",
        related="company_id.mpesa_passkey",
        readonly=False
    )
    mpesa_shortcode = fields.Char(
        string="Business Shortcode / Till Number",
        related="company_id.mpesa_shortcode",
        readonly=False
    )
    
    # C2B Registration Status
    mpesa_c2b_registered = fields.Boolean(
        string="C2B URLs Registered",
        related="company_id.mpesa_c2b_registered",
        readonly=True
    )
    mpesa_c2b_registered_date = fields.Datetime(
        string="Registration Date",
        related="company_id.mpesa_c2b_registered_date",
        readonly=True
    )
    
    # Callback URL (computed)
    mpesa_callback_url = fields.Char(
        string="Callback URL",
        compute="_compute_callback_url",
        readonly=True
    )
    
    @api.depends('company_id')
    def _compute_callback_url(self):
        """Compute the callback URL based on current server"""
        for record in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            record.mpesa_callback_url = f"{base_url}/mpesa/callback"
    
    def action_register_c2b_urls(self):
        """Register C2B validation and confirmation URLs with Safaricom"""
        self.ensure_one()
        
        if not self.mpesa_shortcode:
            raise UserError("Please configure your Business Shortcode first.")
        
        if not self.mpesa_consumer_key or not self.mpesa_consumer_secret:
            raise UserError("Please configure your M-Pesa Consumer Key and Secret first.")
        
        try:
            # Determine API URL based on environment
            if self.mpesa_environment == 'production':
                oauth_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
                register_url = "https://api.safaricom.co.ke/mpesa/c2b/v1/registerurl"
            else:
                oauth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
                register_url = "https://sandbox.safaricom.co.ke/mpesa/c2b/v1/registerurl"
            
            _logger.info("="*70)
            _logger.info("REGISTERING C2B URLs WITH SAFARICOM")
            _logger.info("="*70)
            _logger.info(f"Environment: {self.mpesa_environment}")
            _logger.info(f"Account Type: {self.mpesa_account_type}")
            _logger.info(f"Shortcode: {self.mpesa_shortcode}")
            
            # Get access token
            _logger.info("→ Getting access token...")
            auth_response = requests.get(
                oauth_url,
                auth=(self.mpesa_consumer_key, self.mpesa_consumer_secret),
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=30
            )
            
            if auth_response.status_code != 200:
                raise UserError(f"Failed to get access token: {auth_response.text}")
            
            access_token = auth_response.json().get('access_token')
            _logger.info("✓ Access token obtained")
            
            # Register URLs
            _logger.info("→ Registering C2B URLs...")
            callback_url = self.mpesa_callback_url
            
            payload = {
                "ShortCode": self.mpesa_shortcode,
                "ResponseType": "Completed",
                "ConfirmationURL": callback_url,
                "ValidationURL": callback_url
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            
            register_response = requests.post(
                register_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            response_data = register_response.json()
            _logger.info(f"Response: {response_data}")
            
            if register_response.status_code == 200 and response_data.get('ResponseCode') == '0':
                # Mark as registered
                self.company_id.write({
                    'mpesa_c2b_registered': True,
                    'mpesa_c2b_registered_date': fields.Datetime.now()
                })
                
                _logger.info("✓ C2B URLs registered successfully")
                
                # Show success notification with sticky option for visibility
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '✅ Registration Successful!',
                        'message': 'Your C2B callback URLs have been successfully registered with Safaricom. You can now receive direct customer payments.',
                        'type': 'success',
                        'sticky': True,  # Make it sticky so user must dismiss it
                        'next': {'type': 'ir.actions.act_window_close'},  # Refresh the view
                    }
                }
            else:
                error_msg = response_data.get('errorMessage') or response_data.get('ResponseDescription') or 'Registration failed'
                _logger.error(f"❌ Registration failed: {error_msg}")
                raise UserError(f"C2B Registration Failed: {error_msg}")
                
        except requests.exceptions.Timeout:
            raise UserError("Request timeout. Please check your internet connection and try again.")
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Request exception: {str(e)}")
            raise UserError(f"Network error: {str(e)}")
        except Exception as e:
            _logger.error(f"❌ Unexpected error: {str(e)}")
            raise UserError(f"An error occurred: {str(e)}")
    
    def action_test_connection(self):
        """Test M-Pesa API connection"""
        self.ensure_one()
        
        if not self.mpesa_consumer_key or not self.mpesa_consumer_secret:
            raise UserError("Please configure your M-Pesa Consumer Key and Secret first.")
        
        try:
            # Determine OAuth URL based on environment
            if self.mpesa_environment == 'production':
                oauth_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            else:
                oauth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            
            _logger.info("Testing M-Pesa connection...")
            
            response = requests.get(
                oauth_url,
                auth=(self.mpesa_consumer_key, self.mpesa_consumer_secret),
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=30
            )
            
            if response.status_code == 200:
                _logger.info("✓ Connection test successful")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '✅ Connection Successful!',
                        'message': f'Successfully connected to M-Pesa {self.mpesa_environment.upper()} environment. Your credentials are valid.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                _logger.error(f"❌ Connection test failed: {response.text}")
                raise UserError(f"Connection failed: {response.text}")
                
        except requests.exceptions.Timeout:
            raise UserError("Connection timeout. Please check your internet connection.")
        except Exception as e:
            raise UserError(f"Connection error: {str(e)}")