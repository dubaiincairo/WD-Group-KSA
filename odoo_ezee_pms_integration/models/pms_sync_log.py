from odoo import models, fields

class PMSSyncLog(models.Model):
    _name = 'pms.sync.log'
    _description = 'PMS Sync Log'
    _order = 'create_date desc'

    hotel_id = fields.Many2one('pms.credentials', string='Hotel')
    api_type = fields.Selection([
        ('sales', 'Sales'),
        ('receipt', 'Receipt'),
        ('payment', 'Payment'),
        ('journal', 'Journal'),
        ('incidental', 'Incidental'),
        ('config', 'Configuration'),
    ], string='API Type')
    sync_date = fields.Date(string='Sync Date')
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ], string='Status')
    request_payload = fields.Text(string='Request Payload')
    response_payload = fields.Text(string='Response Payload')
    error_message = fields.Text(string='Error Message')
