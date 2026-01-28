from odoo import models, fields

class PMSAccountMapping(models.Model):
    _name = 'pms.account.mapping'
    _description = 'PMS Account Mapping'

    hotel_id = fields.Many2one('pms.credentials', string='Hotel', required=True)
    pms_account_id = fields.Char(string='PMS Account ID', required=True)
    pms_account_name = fields.Char(string='PMS Account Name')
    account_id = fields.Many2one('account.account', string='Odoo Account')

class PMSTaxMapping(models.Model):
    _name = 'pms.tax.mapping'
    _description = 'PMS Tax Mapping'

    hotel_id = fields.Many2one('pms.credentials', string='Hotel', required=True)
    pms_tax_id = fields.Char(string='PMS Tax ID', required=True)
    pms_tax_name = fields.Char(string='PMS Tax Name')
    tax_id = fields.Many2one('account.tax', string='Odoo Tax')

class PMSPaymentMapping(models.Model):
    _name = 'pms.payment.mapping'
    _description = 'PMS Payment Method Mapping'

    hotel_id = fields.Many2one('pms.credentials', string='Hotel', required=True)
    pms_payment_id = fields.Char(string='PMS Payment ID')
    pms_payment_type = fields.Char(string='PMS Payment Type', required=True)
    journal_id = fields.Many2one('account.journal', string='Odoo Journal')
