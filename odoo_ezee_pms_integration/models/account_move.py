from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    pms_tran_id = fields.Char(string='PMS Transaction ID', copy=False, index=True)
    pms_hotel_id = fields.Many2one('pms.credentials', string='PMS Hotel', copy=False)
    pms_reference = fields.Char(string='PMS Reference', copy=False)
    
    # eZee Info fields
    ezee_id = fields.Char(string='Ezee ID', readonly=True, copy=False)
    ezee_guest_name = fields.Char(string='Guest Name', readonly=True, copy=False)
    ezee_reservation_number = fields.Char(string='Reservation Number', readonly=True, copy=False)
    ezee_folio_number = fields.Char(string='Folio Number', readonly=True, copy=False)
    ezee_type = fields.Char(string='Type', readonly=True, copy=False)
    ezee_room_number = fields.Char(string='Room Number', readonly=True, copy=False)
    ezee_checkin_date = fields.Date(string='Check-In Date', readonly=True, copy=False)
    ezee_checkout_date = fields.Date(string='Check-Out Date', readonly=True, copy=False)
    ezee_receipt_no = fields.Char(string='Receipt No', readonly=True, copy=False)
    ezee_amount = fields.Float(string='Amount', readonly=True, copy=False)
    is_sale_installed = fields.Boolean()
    _sql_constraints = [
        ('pms_tran_id_unique', 'unique(pms_tran_id, pms_hotel_id, move_type)', 'PMS Transaction ID must be unique per hotel and type!')
    ]

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    pms_tran_id = fields.Char(string='PMS Transaction ID', copy=False, index=True)
    pms_hotel_id = fields.Many2one('pms.credentials', string='PMS Hotel', copy=False)
    pms_reference = fields.Char(string='PMS Reference', copy=False)
    # eZee Info fields
    ezee_id = fields.Char(string='Ezee ID', readonly=True, copy=False)
    ezee_guest_name = fields.Char(string='Guest Name', readonly=True, copy=False)
    ezee_reservation_number = fields.Char(string='Reservation Number', readonly=True, copy=False)
    ezee_folio_number = fields.Char(string='Folio Number', readonly=True, copy=False)
    ezee_type = fields.Char(string='Type', readonly=True, copy=False)
    ezee_room_number = fields.Char(string='Room Number', readonly=True, copy=False)
    ezee_checkin_date = fields.Date(string='Check-In Date', readonly=True, copy=False)
    ezee_checkout_date = fields.Date(string='Check-Out Date', readonly=True, copy=False)
    ezee_receipt_no = fields.Char(string='Receipt No', readonly=True, copy=False)
    ezee_amount = fields.Float(string='Amount', readonly=True, copy=False)
    
    _sql_constraints = [
        ('pms_tran_id_unique', 'unique(pms_tran_id, pms_hotel_id, payment_type)', 'PMS Transaction ID must be unique per hotel and payment type!')
    ]