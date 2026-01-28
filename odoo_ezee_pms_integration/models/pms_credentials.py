from odoo import models, fields, api

class PMSCredentials(models.Model):
    _name = 'pms.credentials'
    _description = 'PMS Credentials'

    name = fields.Char(string='Hotel Name', required=True)
    hotel_code = fields.Char(string='Hotel Code', required=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True, password=True)
    auth_code = fields.Char(string='Auth Code', readonly=True)
    working_date = fields.Date(string='Working Date', readonly=True)
    currency_code = fields.Char(string='Currency Code', readonly=True)
    
    journal_id = fields.Many2one('account.journal', string='Default Journal')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    active = fields.Boolean(default=True)

    def action_test_connection(self):
        """Test connection to eZee PMS API and return user notification"""
        from ..services.ezee_api_service import eZeeAPIService
        from odoo.exceptions import UserError
        
        service = eZeeAPIService(self)
        success, message = service.login()

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful!',
                    'message': f'Successfully connected to eZee PMS for {self.name}.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': f'Error: {message}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_scheduled_sync(self):
        """Called by cron to sync all active hotels for the previous day"""
        from odoo.fields import Date
        from datetime import timedelta
        yesterday = Date.today() - timedelta(days=1)
        
        for hotel in self:
            wizard = self.env['pms.sync.wizard'].create({
                'hotel_ids': [(4, hotel.id)],
                'from_date': yesterday,
                'to_date': yesterday,
            })
            wizard.action_sync()

    def action_pull_config(self):
        """Fetch master data/configuration values from eZee PMS"""
        from ..services.ezee_api_service import eZeeAPIService
        service = eZeeAPIService(self)
        
        # Ensure logged in
        if not self.auth_code:
            service.login()
        
        data = service.fetch_data('config')
        
        if data:
            self._process_config_data(data)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Configuration Pulled',
                    'message': 'Master data successfully pulled and mapping tables updated.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Failed to Pull Configuration',
                    'message': 'Check Sync Logs for details.',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _process_config_data(self, data):
        """Parse configuration data and populate mapping models"""
        if not data:
            return

        records = []
        if isinstance(data, dict):
            records = data.get('data', [])
        elif isinstance(data, list):
            records = data

        if not isinstance(records, list):
            return

        for rec in records:
            desc_type = str(rec.get('descriptiontype', '')).upper()
            unk_id = rec.get('descriptionunkid')
            name = rec.get('description')

            if not unk_id:
                continue

            if desc_type in ['ROOM TYPE', 'SOURCE', 'EXTRA CHARGE', 'REVENUE TYPE', 'ROOM CHARGE', 'DISCOUNT', 'PAID OUT', 'CITY LEDGER']:
                mapping = self.env['pms.account.mapping'].search([
                    ('hotel_id', '=', self.id),
                    ('pms_account_id', '=', str(unk_id))
                ], limit=1)
                
                vals = {
                    'pms_account_name': name,
                    'hotel_id': self.id,
                    'pms_account_id': str(unk_id),
                }
                
                if mapping:
                    mapping.write({'pms_account_name': name})
                else:
                    vals['account_id'] = self.journal_id.default_account_id.id or False
                    self.env['pms.account.mapping'].create(vals)

            elif 'TAX' in desc_type:
                mapping = self.env['pms.tax.mapping'].search([
                    ('hotel_id', '=', self.id),
                    ('pms_tax_id', '=', str(unk_id))
                ], limit=1)
                
                vals = {
                    'pms_tax_name': name,
                    'hotel_id': self.id,
                    'pms_tax_id': str(unk_id),
                }
                
                if mapping:
                    mapping.write({'pms_tax_name': name})
                else:
                    self.env['pms.tax.mapping'].create(vals)

            elif desc_type == 'PAYMENT TYPE':
                if str(unk_id) == '1' and name == 'Payment Type':
                    continue
                    
                mapping = self.env['pms.payment.mapping'].search([
                    ('hotel_id', '=', self.id),
                    '|',
                    ('pms_payment_id', '=', str(unk_id)),
                    ('pms_payment_type', '=', name)
                ], limit=1)
                
                vals = {
                    'pms_payment_type': name,
                    'pms_payment_id': str(unk_id),
                    'hotel_id': self.id,
                }
                
                if mapping:
                    mapping.write(vals)
                else:
                    vals['journal_id'] = self.journal_id.id or False
                    self.env['pms.payment.mapping'].create(vals)
