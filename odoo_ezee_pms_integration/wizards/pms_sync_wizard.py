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
        for record in data:
            # Check if already exists
            existing = self.env['account.move'].search([
                ('pms_tran_id', '=', record['record_id']),
                ('pms_hotel_id', '=', hotel.id),
                ('move_type', '=', 'out_invoice')
            ])
            if existing: continue

            # Find or create partner
            partner = self._get_or_create_partner(record)
            
            # Create Invoice
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': record['record_date'],
                'pms_tran_id': record['record_id'],
                'pms_hotel_id': hotel.id,
                'pms_reference': record.get('reference3'), # Reservation No
                'journal_id': hotel.journal_id.id,
                'invoice_line_ids': [],
            }

            for detail in record.get('detail', []):
                # Map account
                mapping = self.env['pms.account.mapping'].search([
                    ('hotel_id', '=', hotel.id),
                    ('pms_account_id', '=', str(detail.get('reference_id')))
                ], limit=1)
                
                if mapping:
                    invoice_vals['invoice_line_ids'].append((0, 0, {
                        'name': detail.get('reference_name') or 'PMS Charge',
                        'account_id': mapping.account_id.id,
                        'price_unit': float(detail.get('amount', 0)),
                        'quantity': 1,
                        'analytic_distribution': {str(hotel.analytic_account_id.id): 100} if hotel.analytic_account_id else {},
                    }))
            
            if invoice_vals['invoice_line_ids']:
                self.env['account.move'].create(invoice_vals)

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
