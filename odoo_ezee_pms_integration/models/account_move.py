from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    pms_tran_id = fields.Char(string='PMS Transaction ID', copy=False, index=True)
    pms_hotel_id = fields.Many2one('pms.credentials', string='PMS Hotel', copy=False)
    pms_reference = fields.Char(string='PMS Reference', copy=False)

    _sql_constraints = [
        ('pms_tran_id_unique', 'unique(pms_tran_id, pms_hotel_id, move_type)', 'PMS Transaction ID must be unique per hotel and type!')
    ]

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    pms_tran_id = fields.Char(string='PMS Transaction ID', copy=False, index=True)
    pms_hotel_id = fields.Many2one('pms.credentials', string='PMS Hotel', copy=False)
    pms_reference = fields.Char(string='PMS Reference', copy=False)

    _sql_constraints = [
        ('pms_tran_id_unique', 'unique(pms_tran_id, pms_hotel_id, move_type)', 'PMS Transaction ID must be unique per hotel and type!')
    ]