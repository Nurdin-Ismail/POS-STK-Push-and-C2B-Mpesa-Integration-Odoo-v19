from odoo import models, fields

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    # M-Pesa fields
    mpesa_receipt_number = fields.Char(string='M-Pesa Receipt', readonly=True)
    mpesa_phone_number = fields.Char(string='M-Pesa Phone', readonly=True)
    mpesa_customer_name = fields.Char(string='Customer Name', readonly=True)
    mpesa_transaction_date = fields.Char(string='Transaction Date', readonly=True)
    mpesa_callback_id = fields.Many2one('mpesa.callback.entry', string='M-Pesa Callback', readonly=True)