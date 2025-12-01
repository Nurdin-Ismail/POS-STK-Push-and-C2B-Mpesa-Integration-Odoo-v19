from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    # M-Pesa Environment
    mpesa_environment = fields.Selection([
        ('sandbox', 'Sandbox (Testing)'),
        ('production', 'Production (Live)')
    ], string='M-Pesa Environment', default='sandbox', required=True)
    
    # M-Pesa Account Type
    mpesa_account_type = fields.Selection([
        ('paybill', 'Paybill'),
        ('till', 'Buy Goods (Till Number)')
    ], string='Account Type', default='paybill', required=True)
    
    # M-Pesa Credentials
    mpesa_consumer_key = fields.Char(string='Consumer Key')
    mpesa_consumer_secret = fields.Char(string='Consumer Secret')
    mpesa_passkey = fields.Char(string='Lipa Na M-Pesa Passkey')
    mpesa_shortcode = fields.Char(string='Business Shortcode / Till Number')
    
    # C2B Registration Status
    mpesa_c2b_registered = fields.Boolean(
        string='C2B URLs Registered',
        default=False,
        help='Indicates whether C2B callback URLs have been registered with Safaricom'
    )
    mpesa_c2b_registered_date = fields.Datetime(
        string='C2B Registration Date',
        readonly=True
    )