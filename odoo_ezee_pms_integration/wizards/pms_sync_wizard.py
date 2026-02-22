from odoo import models, fields, api
from datetime import datetime
import logging
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

class PMSSyncWizard(models.TransientModel):
    _name = 'pms.sync.wizard'
    _description = 'PMS Sync Wizard'

    hotel_ids = fields.Many2many('pms.credentials', string='Hotels', required=True)
    from_date = fields.Date(string='From Date', required=True, default=fields.Date.context_today)
    to_date = fields.Date(string='To Date', required=True, default=fields.Date.context_today)
    
    sync_sales = fields.Boolean(string='Sync Sales', default=True)
    sync_receipts = fields.Boolean(string='Sync Receipts', default=True)
    sync_payments = fields.Boolean(string='Sync Payments', default=True)
    sync_journals = fields.Boolean(string='Sync Journals', default=True)
    sync_incidentals = fields.Boolean(string='Sync Incidentals', default=True)

    def action_sync(self):
        for hotel in self.hotel_ids:
            from ..services.ezee_api_service import eZeeAPIService
            service = eZeeAPIService(hotel)
            
            # Ensure logged in
            if not hotel.auth_code:
                service.login()
            
            if self.sync_sales:
                data = service.fetch_data('sales', self.from_date, self.to_date)
                result = self._process_sales(hotel, data)
                if result == "Failed":
                    return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sales Failed',
                    'message': 'Check Sync Logs for details.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
                else:
                   return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sales Successes ',
                    'message': 'Sales pulled',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
            
            if self.sync_receipts:
                data = service.fetch_data('receipt', self.from_date, self.to_date)
                result = self._process_receipts(hotel, data)
                if result == "Failed":
                    return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Receipts Failed',
                    'message': 'Check Sync Logs for details.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
                else:
                   return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Receipts Successes ',
                    'message': 'Receipts pulled',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

            if self.sync_payments:
                data = service.fetch_data('payment', self.from_date, self.to_date)
                result = self._process_payments(hotel, data)
                if result == "Failed":
                    return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Payment Failed',
                    'message': 'Check Sync Logs for details.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
                else:
                   return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Payment Successes ',
                    'message': 'Payment pulled',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
            if self.sync_journals:
                data = service.fetch_data('journal', self.from_date, self.to_date)
                self._process_journals(hotel, data)

            if self.sync_incidentals:
                data = service.fetch_data('incidental', self.from_date, self.to_date)
                self._process_incidentals(hotel, data)
       

    def _process_sales(self, hotel, data):
        if not data: return "Failed"
        
        company= self.env['res.company'].search([('hotel_id', '=', hotel.id)], limit=1)

        records = data.get('data', []) if isinstance(data, dict) else data
        if not records or not isinstance(records, list): return

        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)

        for record in records:
            tran_id = record.get('record_id')
            if not tran_id: continue

            
            existing = self.env['account.move'].search([
                ('pms_tran_id', '=', tran_id),
                ('pms_hotel_id', '=', hotel.id),
                ('move_type', '=', 'out_invoice')
            ])
            if existing:
                existing.button_draft()

            
            partner = self._get_or_create_partner(record)


            ezee_total = self._parse_ezee_amount(record.get('total_amount') or record.get('TotalAmount') or record.get('Amount'))

            if record.get('record_id')=='S31309-03':
                print ("IT IS")
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': self._parse_ezee_date(record.get('record_date')) or fields.Date.today(),
                'pms_tran_id': tran_id,
                'pms_hotel_id': hotel.id,
                'pms_reference': record.get('reference3'), # Reservation No
                'journal_id': hotel.journal_id.id,
                'invoice_line_ids': [],
                'company_id': company.id if company else self.env.company.id,
                'ezee_id': record.get('record_id'),
                'ezee_guest_name': record.get('reference5'),
                'ezee_reservation_number': record.get('reference3'),
                'ezee_folio_number': record.get('reference4'),
                'ezee_type': record.get('reference14'),
                'ezee_room_number': record.get('reference13'),
                'ezee_checkin_date': self._parse_ezee_date(record.get('reference1')),
                'ezee_checkout_date': self._parse_ezee_date(record.get('reference2')),
                'ezee_receipt_no': record.get('reference8'), # Bill No
                'ezee_amount': ezee_total,
            }
            lines = {}
            tax_ids = []
            for detail in record.get('detail', []):
                record_id = detail['detail_record_id']
                amount = float(detail.get('amount', 0) or 0)
                ref_name = detail.get('reference_name')
                line_name = detail.get('charge_name') or'PMS Charge'
                amount = self._parse_ezee_amount(detail.get('amount'))
                if record_id not in lines:
                    tax_ids = []
                    mapping = self.env['pms.account.mapping'].search([
                        ('pms_account_header_id', '=',
                         int(detail.get('reference_id')) if detail.get('reference_id') else 0),
                    ], limit=1)
                    account_id = False
                    if mapping:
                        account_id = mapping.account_id.id
                    elif hotel.journal_id.default_account_id:
                        account_id = hotel.journal_id.default_account_id.id
                    elif income_account:
                        account_id = income_account.id
                    lines[record_id] = {
                            'name': line_name,
                            'discount': 0,
                            'account_id': account_id,
                            'price_unit': amount,
                            'quantity': 1,
                            'tax_ids':[],
                            'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                        }

                if ref_name == 'Taxes':
                    charge_name = detail.get('charge_name')
                    tax_id = self.env['account.tax'].search([
                        ('type_tax_use', '=', 'sale'),
                        ('name', '=', charge_name),
                    ], limit=1)
                    
                    if tax_id:
                        if not tax_id.include_base_amount:
                            tax_id.include_base_amount = True  # or fix it in UI
                        # أضف المعرف للمصفوفة الخاصة بهذا السطر
                        if tax_id.id not in lines[record_id]['tax_ids']:
                            lines[record_id]['tax_ids'].append(tax_id.id)

            if lines:
                for record_id, line_vals in lines.items():
                    if line_vals['tax_ids']:
                        # نقوم بجلب الضرائب وترتيبها حسب الـ Sequence الموجود في إعدادات أودو
                        # إذا كنت وضعت الـ 15% بـ sequence أقل (مثلاً 5) والـ 2.5% بـ sequence (مثلاً 10)
                        # فإن أودو سيطبقها بالترتيب الصحيح
                        ordered_taxes = self.env['account.tax'].browse(line_vals['tax_ids']).sorted(key=lambda t: t.sequence)
                        
                        # نضع الضرائب المرتبة في سطر الفاتورة
                        line_vals['tax_ids'] = [(6, 0, ordered_taxes.ids)]
                    
                    invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                    
            sum_lines = sum(line[2]['price_unit'] for line in invoice_vals['invoice_line_ids'])

            # If total doesn't match or no lines, adjust or create fallback
            # if abs(sum_lines - ezee_total) > 0.01:
            #     diff = ezee_total - sum_lines
            #     fallback_account = hotel.journal_id.default_account_id.id or (income_account.id if income_account else False)
            #     if fallback_account:
            #         invoice_vals['invoice_line_ids'].append((0, 0, {
            #             'name': 'PMS Sales Adjustment' if sum_lines > 0 else 'PMS Sales Import',
            #             'account_id': fallback_account,
            #             'price_unit': diff,
            #             'quantity': 1,
            #             'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
            #         }))

            if invoice_vals['invoice_line_ids']:
                inv = self.env['account.move'].create(invoice_vals)
                    # Force full recomputation so sequential tax logic kicks in
                # inv.with_context(check_move_validity=False)._onchange_invoice_line_ids()
                inv._compute_tax_totals()
                # inv._check_balanced()
                # inv.action_post()
        return "Success"
    def _parse_ezee_amount(self, value):
        """Robust float parsing for eZee amounts"""
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            
            clean_value = str(value).replace(',', '').strip()
            return float(clean_value)
        except:
            return 0.0

    def _parse_ezee_date(self, date_str):
        """Helper to parse dates from eZee API (DD/MM/YYYY or YYYY-MM-DD)"""
        if not date_str:
            return False
        
        date_str = str(date_str).split(' ')[0]
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            # Try DD/MM/YYYY (eZee UI format)
            try:
                return datetime.strptime(date_str, '%d/%m/%Y').date()
            except:
                try:
                    return fields.Date.from_string(date_str)
                except:
                    return False

    def _get_or_create_partner(self, record):
        name = record.get('reference5') or 'Guest'
        email = record.get('reference19')
        partner = self.env['res.partner'].search([('name', '=', name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': name,
                'email': email,
                'property_account_receivable_id': self.env.company.account_default_pos_receivable_account_id.id or self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1).id
            })
        return partner

    def _process_receipts(self, hotel, data):
        company= self.env['res.company'].search([('hotel_id', '=', hotel.id)], limit=1)
        if not data or data.get('status') != 'Success': return "Failed"
        for group in data.get('data', []):
            type = group.get('type')
            for record in group.get('data', []):
                existing = self.env['account.payment'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference2')})
                journal_id = hotel.journal_id
                if type == 'Advance Deposit':
                    if 'Cash' in record.get('reference14') :
                        journal_id= self.env['account.journal'].search([('name', '=', 'Cash')], limit=1) or journal_id
                    else:
                        journal_id= self.env['account.journal'].search([('name', '=', 'Bank')], limit=1) or journal_id
                if type == 'Received From Guest' or type == 'Received From Cityledger':
                       if 'Cash' in record.get('reference14') :
                        journal_id= self.env['account.journal'].search([('name', '=', 'Cash')], limit=1) or journal_id
                       else:
                        journal_id= self.env['account.journal'].search([('name', '=', 'Bank')], limit=1) or journal_id
                payment_method_line = (
                        journal_id._get_available_payment_method_lines('inbound')[:1]
                        or journal_id.inbound_payment_method_line_ids[:1]
                )
                payment_vals = {
                    'payment_type': 'inbound',
                    'company_id': company.id if company else self.env.company.id,
                    'partner_type': 'customer',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'), # Receipt No
                    'journal_id': journal_id.id if journal_id else hotel.journal_id.id,
                    'partner_id': partner.id,
                    'payment_method_line_id': payment_method_line.id,
                    'amount': self._parse_ezee_amount(record.get('gross_amount') or record.get('TotalAmount') or record.get('Amount')),
                    'ezee_reservation_number': record.get('reference3'),
                    }

                payment = self.env['account.payment'].create(payment_vals)
                # payment.post()
        return "Success"

    def _process_payments(self, hotel, data):
        company = self.env['res.company'].search([('hotel_id', '=', hotel.id)], limit=1)
        if not data or data.get('status') != 'Success':
            return "Failed"
        for group in data.get('data', []):
            type = group.get('type')
            for record in group.get('data', []):
                existing = self.env['account.payment'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference2')})
                journal_id = hotel.journal_id
                if type == 'General Expense':
                    if 'Cash' in record.get('reference14'):
                        journal_id = self.env['account.journal'].search([('name', '=', 'Cash')], limit=1) or journal_id
                    else:
                        journal_id = self.env['account.journal'].search([('name', '=', 'Bank')], limit=1) or journal_id
                if type == 'Advance Deposit Refund':
                    if 'Cash' in record.get('reference14'):
                        journal_id = self.env['account.journal'].search([('name', '=', 'Cash')], limit=1) or journal_id
                    else:
                        journal_id = self.env['account.journal'].search([('name', '=', 'Bank')], limit=1) or journal_id

                if type == 'Guest Refund' or type == 'Cityledger Refund':
                    if 'Cash' in record.get('reference14'):
                        journal_id = self.env['account.journal'].search([('name', '=', 'Cash')], limit=1) or journal_id
                    else:
                        journal_id = self.env['account.journal'].search([('name', '=', 'Bank')], limit=1) or journal_id
                payment_method_line = (
                        journal_id._get_available_payment_method_lines('outbound')[:1]
                        or journal_id.inbound_payment_method_line_ids[:1]
                )
                payment_vals = {
                    'payment_type': 'outbound',
                    'company_id': company.id if company else self.env.company.id,
                    'partner_type': 'supplier',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'),  # Receipt No
                    'journal_id': journal_id.id if journal_id else hotel.journal_id.id,
                    'partner_id': partner.id,
                    'payment_method_line_id': payment_method_line.id,
                    'amount': self._parse_ezee_amount(
                        record.get('gross_amount') or record.get('TotalAmount') or record.get('Amount')),
                    'ezee_reservation_number': record.get('reference3'),
                }

                payment = self.env['account.payment'].create(payment_vals)
                # payment.post()
        return "Success"


    def _process_journals(self, hotel, data):
        if not data or data.get('status') != 'Success': return
        for group in data.get('data', []):
            for record in group.get('data', []):
                existing = self.env['account.move'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                    ('move_type', '=', 'entry')
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference2') or 'Guest'})

                move_vals = {
                    'move_type': 'entry',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'),
                    'journal_id': hotel.journal_id.id,
                    'line_ids': [],
                }

                total_debit = 0.0
                total_credit = 0.0
                for detail in record.get('detail', []):
                    mapping = self.env['pms.account.mapping'].search([
                        ('hotel_id', '=', hotel.id),
                        '|',
                        ('pms_account_id', '=', str(detail.get('reference_id'))),
                        ('pms_account_name', '=', detail.get('reference_value'))
                    ], limit=1)
                    account_id = mapping.account_id.id if mapping else None
                    if not account_id: continue

                    amount = float(detail.get('amount', 0))
                    
                    debit = amount if detail.get('tran_type') == 'Cr' else 0.0
                    credit = amount if detail.get('tran_type') == 'Dr' else 0.0

                    line_name = (mapping.pms_account_name if mapping else False) or \
                                detail.get('reference_value') or \
                                (mapping.account_id.name if mapping else False) or \
                                'PMS Journal'

                    move_vals['line_ids'].append((0, 0, {
                        'name': line_name,
                        'partner_id': partner.id,
                        'account_id': account_id,
                        'debit': debit,
                        'credit': credit,
                        'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                    }))
                    total_debit += debit
                    total_credit += credit
                
                if move_vals['line_ids'] and abs(total_debit - total_credit) > 0.01:
                    diff = total_debit - total_credit
                    receivable_account = partner.property_account_receivable_id or self.env['account.account'].search([
                        ('account_type', '=', 'asset_receivable'),
                        ('company_id', '=', self.env.company.id)
                    ], limit=1)
                    if receivable_account:
                        move_vals['line_ids'].append((0, 0, {
                            'name': 'PMS Journal Balancing',
                            'partner_id': partner.id,
                            'account_id': receivable_account.id,
                            'debit': -diff if diff < 0 else 0.0,
                            'credit': diff if diff > 0 else 0.0,
                            'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                        }))

                if move_vals['line_ids']:
                    self.env['account.move'].create(move_vals).action_post()

    def _process_incidentals(self, hotel, data):
        if not data or data.get('status') != 'Success': return
        for group in data.get('data', []):
            for record in group.get('data', []):
                existing = self.env['account.move'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                    ('move_type', '=', 'out_invoice')
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference1')})
                invoice_vals = {
                    'move_type': 'out_invoice',
                    'partner_id': partner.id,
                    'invoice_date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference3'),
                    'journal_id': hotel.journal_id.id,
                    'invoice_line_ids': [],
                }

                for detail in record.get('detail', []):
                    if detail.get('tran_type') == 'Cr': # Revenue side
                        mapping = self.env['pms.account.mapping'].search([
                            ('hotel_id', '=', hotel.id),
                            ('pms_account_id', '=', str(detail.get('reference_id')))
                        ], limit=1)
                        account_id = mapping.account_id.id if mapping else None
                        if not account_id: continue

                        invoice_vals['invoice_line_ids'].append((0, 0, {
                            'name': detail.get('reference_value') or 'Incidental Charge',
                            'account_id': account_id,
                            'price_unit': float(detail.get('amount', 0)),
                            'quantity': 1,
                            'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                        }))
                
                if invoice_vals['invoice_line_ids']:
                    self.env['account.move'].create(invoice_vals)
