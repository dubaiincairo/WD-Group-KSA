from odoo import models, fields, api
from datetime import datetime

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
                self._process_sales(hotel, data)
            
            if self.sync_receipts:
                data = service.fetch_data('receipt', self.from_date, self.to_date)
                self._process_receipts(hotel, data)

            if self.sync_payments:
                data = service.fetch_data('payment', self.from_date, self.to_date)
                self._process_payments(hotel, data)

            if self.sync_journals:
                data = service.fetch_data('journal', self.from_date, self.to_date)
                self._process_journals(hotel, data)

            if self.sync_incidentals:
                data = service.fetch_data('incidental', self.from_date, self.to_date)
                self._process_incidentals(hotel, data)

    def _process_sales(self, hotel, data):
        if not data: return
        
        # Handle the list structure or wrapped data
        records = data.get('data', []) if isinstance(data, dict) else data
        if not records or not isinstance(records, list): return

        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)

        for record in records:
            tran_id = record.get('record_id')
            if not tran_id: continue

            # Check if already exists
            existing = self.env['account.move'].search([
                ('pms_tran_id', '=', tran_id),
                ('pms_hotel_id', '=', hotel.id),
                ('move_type', '=', 'out_invoice')
            ])
            if existing: continue

            # Find or create partner
            partner = self._get_or_create_partner(record)
            
            # Use the total_amount from the header if available
            ezee_total = self._parse_ezee_amount(record.get('total_amount') or record.get('TotalAmount') or record.get('Amount'))
            
            # Create Invoice
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': self._parse_ezee_date(record.get('record_date')) or fields.Date.today(),
                'pms_tran_id': tran_id,
                'pms_hotel_id': hotel.id,
                'pms_reference': record.get('reference3'), # Reservation No
                'journal_id': hotel.journal_id.id,
                'invoice_line_ids': [],
                
                # eZee Info fields mapped to response structure
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

            for detail in record.get('detail', []):
                # Try to map account by ID or Name
                mapping = self.env['pms.account.mapping'].search([
                    ('hotel_id', '=', hotel.id),
                    '|',
                    ('pms_account_id', '=', str(detail.get('reference_id'))),
                    ('pms_account_name', '=', detail.get('reference_name'))
                ], limit=1)
                
                amount = self._parse_ezee_amount(detail.get('amount'))
                if amount != 0 or detail.get('reference_name'):
                    # Determine account
                    account_id = False
                    if mapping:
                        account_id = mapping.account_id.id
                    elif hotel.journal_id.default_account_id:
                        account_id = hotel.journal_id.default_account_id.id
                    elif income_account:
                        account_id = income_account.id
                    
                    if account_id:
                        invoice_vals['invoice_line_ids'].append((0, 0, {
                            'name': detail.get('reference_name') or 'PMS Charge',
                            'account_id': account_id,
                            'price_unit': amount,
                            'quantity': 1,
                            'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                        }))
            
            # Sum up lines to check if we matched everything
            sum_lines = sum(line[2]['price_unit'] for line in invoice_vals['invoice_line_ids'])
            
            # If total doesn't match or no lines, adjust or create fallback
            if abs(sum_lines - ezee_total) > 0.01:
                diff = ezee_total - sum_lines
                fallback_account = hotel.journal_id.default_account_id.id or (income_account.id if income_account else False)
                if fallback_account:
                    invoice_vals['invoice_line_ids'].append((0, 0, {
                        'name': 'PMS Sales Adjustment' if sum_lines > 0 else 'PMS Sales Import',
                        'account_id': fallback_account,
                        'price_unit': diff,
                        'quantity': 1,
                        'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                    }))

            if invoice_vals['invoice_line_ids']:
                self.env['account.move'].create(invoice_vals)

    def _parse_ezee_amount(self, value):
        """Robust float parsing for eZee amounts"""
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            # Handle string with potential commas or extra spaces
            clean_value = str(value).replace(',', '').strip()
            return float(clean_value)
        except:
            return 0.0

    def _parse_ezee_date(self, date_str):
        """Helper to parse dates from eZee API (DD/MM/YYYY or YYYY-MM-DD)"""
        if not date_str:
            return False
        # Strip potential time/whitespace
        date_str = str(date_str).split(' ')[0]
        # Try YYYY-MM-DD (standard JSON)
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
        if not data or data.get('status') != 'Success': return
        for group in data.get('data', []):
            for record in group.get('data', []):
                # Check if already exists
                existing = self.env['account.move'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                    ('move_type', '=', 'out_receipt')
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference2')})
                
                # For receipts, we create a Journal Entry (or Payment)
                # Based on the requirement "Post balanced journal entries"
                move_vals = {
                    'move_type': 'out_receipt',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'), # Receipt No
                    'journal_id': hotel.journal_id.id,
                    'line_ids': [],
                }

                for detail in record.get('detail', []):
                    # Map account based on reference_id or reference_value
                    mapping = self.env['pms.account.mapping'].search([
                        ('hotel_id', '=', hotel.id),
                        ('pms_account_id', '=', str(detail.get('reference_id')))
                    ], limit=1)
                    account_id = mapping.account_id.id if mapping else None
                    if not account_id:
                        # Fallback or default logic
                        continue

                    amount = float(detail.get('amount', 0))
                    move_vals['line_ids'].append((0, 0, {
                        'name': detail.get('reference_value') or 'PMS Receipt',
                        'partner_id': partner.id,
                        'account_id': account_id,
                        'debit': amount if detail.get('tran_type') == 'Dr' else 0.0,
                        'credit': amount if detail.get('tran_type') == 'Cr' else 0.0,
                        'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                    }))
                
                if move_vals['line_ids']:
                    self.env['account.move'].create(move_vals).action_post()

    def _process_payments(self, hotel, data):
        if not data or data.get('status') != 'Success': return
        for group in data.get('data', []):
            for record in group.get('data', []):
                existing = self.env['account.move'].search([
                    ('pms_tran_id', '=', record['tranId']),
                    ('pms_hotel_id', '=', hotel.id),
                    ('move_type', '=', 'entry')
                ])
                if existing: continue

                partner = self._get_or_create_partner({'reference5': record.get('reference2')})
                move_vals = {
                    'move_type': 'entry',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'),
                    'journal_id': hotel.journal_id.id,
                    'line_ids': [],
                }

                for detail in record.get('detail', []):
                    mapping = self.env['pms.account.mapping'].search([
                        ('hotel_id', '=', hotel.id),
                        ('pms_account_id', '=', str(detail.get('reference_id')))
                    ], limit=1)
                    account_id = mapping.account_id.id if mapping else None
                    if not account_id: continue

                    amount = float(detail.get('amount', 0))
                    move_vals['line_ids'].append((0, 0, {
                        'name': detail.get('reference_value') or 'PMS Payment',
                        'partner_id': partner.id,
                        'account_id': account_id,
                        'debit': amount if detail.get('tran_type') == 'Dr' else 0.0,
                        'credit': amount if detail.get('tran_type') == 'Cr' else 0.0,
                        'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                    }))
                
                if move_vals['line_ids']:
                    self.env['account.move'].create(move_vals).action_post()

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

                move_vals = {
                    'move_type': 'entry',
                    'date': record['tran_datetime'],
                    'pms_tran_id': record['tranId'],
                    'pms_hotel_id': hotel.id,
                    'pms_reference': record.get('reference1'),
                    'journal_id': hotel.journal_id.id,
                    'line_ids': [],
                }

                for detail in record.get('detail', []):
                    mapping = self.env['pms.account.mapping'].search([
                        ('hotel_id', '=', hotel.id),
                        ('pms_account_id', '=', str(detail.get('reference_id')))
                    ], limit=1)
                    account_id = mapping.account_id.id if mapping else None
                    if not account_id: continue

                    amount = float(detail.get('amount', 0))
                    move_vals['line_ids'].append((0, 0, {
                        'name': detail.get('reference_value') or 'PMS Journal',
                        'account_id': account_id,
                        'debit': amount if detail.get('tran_type') == 'Dr' else 0.0,
                        'credit': amount if detail.get('tran_type') == 'Cr' else 0.0,
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
