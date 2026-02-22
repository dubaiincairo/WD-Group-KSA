from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'
    hotel_id = fields.Many2one('pms.credentials', string='Hotel')



