{
    'name': 'POS STK Push and C2B Mpesa Integration v19',
    'version': '1.1',
    'category': 'Accounting/Payment',
    'summary': 'Integrate M-Pesa STK Push with Odoo (company-specific credentials)',
    'description': """
M-Pesa Integration for Odoo 19
==============================
Adds company-specific configuration fields for M-Pesa STK Push credentials:
- Consumer Key
- Consumer Secret
- Passkey
- Shortcode
""",
    'depends': ['base', 'point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/mpesa_callback_views.xml',
        'views/pos_payment_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'mpesa_integration/static/src/js/mpesa_stkpush.js',
            'mpesa_integration/static/src/xml/pos_payment_screen_inherit.xml',
            'mpesa_integration/static/src/js/mpesa_callback_popup.js',  
            'mpesa_integration/static/src/xml/mpesa_callback_popup.xml', 
            'mpesa_integration/static/src/css/mpesa_callback_popup.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}