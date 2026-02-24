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
    ezee_rate_plan = fields.Char(string='Rate Plan', readonly=True, copy=False)
    ezee_source = fields.Char(string='Source', readonly=True, copy=False)
    ezee_bill_No=fields.Char(string='Bill No', readonly=True, copy=False)
    ezee_bill_name=fields.Char(string='Bill To Name', readonly=True, copy=False)
    ezee_voucher_no=fields.Char(string='Voucher No', readonly=True, copy=False)
    ezee_voucher_name=fields.Char(string='Voucher Name', readonly=True, copy=False)
    ezee_rate_type=fields.Char(string='Rate Type', readonly=True, copy=False)   
    ezee_market=fields.Char(string='Market', readonly=True, copy=False)
    ezee_company_tax_id=fields.Char(string='Company Tax ID', readonly=True, copy=False)
    ezee_tax_number=fields.Char(string='Tax Number', readonly=True, copy=False)
    is_sale_installed = fields.Boolean()
    ezee_email = fields.Char(string='Email', readonly=True, copy=False)
    ezee_address = fields.Char(string='Address', readonly=True, copy=False)
    ezee_address_line = fields.Char(string='Address Line', readonly=True, copy=False)
    ezee_address1 = fields.Char(string='Address Line 1', readonly=True, copy=False)
    ezee_address2 = fields.Char(string='Address Line 2', readonly=True, copy=False)
    ezee_address_line2 = fields.Char(string='Address Line 2 (Alt)', readonly=True, copy=False)
    ezee_address3 = fields.Char(string='Address Line 3', readonly=True, copy=False)
    ezee_country = fields.Char(string='Country', readonly=True, copy=False)
    ezee_registration_no = fields.Char(string='Registration No.', readonly=True, copy=False)
    ezee_booking_no = fields.Char(string='Booking No. (OTA booking reference)', readonly=True, copy=False)
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