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
