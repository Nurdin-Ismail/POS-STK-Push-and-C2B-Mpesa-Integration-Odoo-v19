from odoo import models, fields, api
import json

class MpesaCallbackEntry(models.Model):
    _name = 'mpesa.callback.entry'
    _description = 'M-Pesa Callback Entry'
    _order = 'create_date desc'
    
    # Callback Type
    callback_type = fields.Selection([
        ('stk', 'STK Push'),
        ('c2b', 'C2B Direct Payment')
    ], string='Payment Type', required=True, readonly=True, index=True)
    
    # STK Push Specific Fields
    merchant_request_id = fields.Char(string='Merchant Request ID', readonly=True, index=True)
    checkout_request_id = fields.Char(string='Checkout Request ID', readonly=True, index=True)
    result_code = fields.Char(string='Result Code', readonly=True)
    result_desc = fields.Char(string='Result Description', readonly=True)
    
    # C2B Specific Fields
    trans_id = fields.Char(string='Transaction ID', readonly=True, index=True, unique=True)
    customer_name = fields.Char(string='Customer Name', readonly=True)
    bill_ref_number = fields.Char(string='Bill Reference', readonly=True)
    transaction_type = fields.Char(string='Transaction Type', readonly=True)  # "Pay Bill" or "Buy Goods"
    
    # Payment Status
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending')
    ], string='Status', compute='_compute_status', store=True, readonly=True)
    
    # Common Transaction Details
    amount = fields.Float(string='Amount', readonly=True, index=True)
    mpesa_receipt_number = fields.Char(string='M-Pesa Receipt Number', readonly=True, index=True, unique=True)
    transaction_date = fields.Char(string='Transaction Date', readonly=True)
    phone_number = fields.Char(string='Phone Number', readonly=True, index=True)
    
    # Reconciliation Fields (for C2B payments)
    is_reconciled = fields.Boolean(string='Reconciled', default=False, readonly=True, index=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True, ondelete='set null')
    reconciled_date = fields.Datetime(string='Reconciled Date', readonly=True)
    
    # Raw Data
    raw_callback_data = fields.Text(string='Raw Callback Data', readonly=True)
    
    # Timestamps
    create_date = fields.Datetime(string='Received Date', readonly=True, index=True)
    
    @api.depends('result_code', 'callback_type')
    def _compute_status(self):
        for record in self:
            if record.callback_type == 'stk':
                # STK Push status based on result_code
                if record.result_code == '0':
                    record.status = 'success'
                elif record.result_code == '1032':
                    record.status = 'cancelled'
                elif record.result_code in ['1', '2032']:
                    record.status = 'failed'
                else:
                    record.status = 'pending'
            elif record.callback_type == 'c2b':
                # C2B callbacks only come for successful transactions
                record.status = 'success'
            else:
                record.status = 'pending'
    
    @api.depends('checkout_request_id', 'trans_id', 'callback_type')
    def _compute_display_name(self):
        for record in self:
            if record.callback_type == 'stk':
                record.display_name = f"{record.checkout_request_id or 'Unknown'} - {record.status or 'Unknown'}"
            elif record.callback_type == 'c2b':
                record.display_name = f"{record.trans_id or 'Unknown'} - {record.status or 'Unknown'}"
            else:
                record.display_name = f"Unknown - {record.status or 'Unknown'}"
    
    def name_get(self):
        result = []
        for record in self:
            if record.callback_type == 'stk':
                name = f"{record.checkout_request_id or 'Unknown'} - {record.status or 'Unknown'}"
            elif record.callback_type == 'c2b':
                name = f"{record.trans_id or 'Unknown'} - {record.status or 'Unknown'}"
            else:
                name = f"Unknown - {record.status or 'Unknown'}"
            result.append((record.id, name))
        return result