{
    'name': 'eZee Absolute PMS Integration',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Synchronize financial data from eZee Absolute PMS to Odoo Accounting',
    'description': """
        This module integrates eZee Absolute PMS with Odoo Accounting.
        It supports synchronization of:
        - Sales (Invoices)
        - Receipts (Payments)
        - Payments (Vendor Bills/Refunds)
        - Journal Entries
        - Incidental Invoices
    """,
    'author': 'WD-Group',
    'depends': ['base','account', 'analytic'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/demo_data.xml',
        'views/pms_credentials_views.xml',
        'views/pms_mapping_views.xml',
        'views/pms_sync_log_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'wizards/pms_sync_wizard_views.xml',
        'views/pms_menus.xml',
        'views/res_company_views.xml'
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
