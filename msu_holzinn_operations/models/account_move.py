from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    bill_type = fields.Selection([
        ('vendor', 'Vendor Bill'),
        ('contractor', 'Contractor Bill'),
    ], string="Bill Type", default='contractor', tracking=True)

    contractor_type = fields.Selection([
        ('inside_premises', 'Inside Premises'),
        ('outside_premises', 'Outside Premises'),
    ], string="Contractor Type", tracking=True)

    work_order_ids = fields.Many2many(
        'work.order', 
        string="Work Orders", 
        domain="[('state', 'not in', ['delivered', 'cancelled'])]",
    )
    department_id = fields.Many2one('hr.department', string="Department")
    credit_note_count = fields.Integer(compute="_compute_credit_note_count")

    def _compute_credit_note_count(self):
        for move in self:
            # Search for credit notes that refer to any of the serial numbers in this bill
            serial_ids = move.invoice_line_ids.mapped('work_order_line_id.id')
            if serial_ids:
                count = self.env['account.move'].search_count([
                    ('move_type', '=', 'in_refund'),
                    ('invoice_line_ids.work_order_line_id', 'in', serial_ids),
                    ('bill_type', '=', 'contractor'),
                ])
                move.credit_note_count = count
            else:
                move.credit_note_count = 0

    def action_view_credit_notes(self):
        self.ensure_one()
        serial_ids = self.invoice_line_ids.mapped('work_order_line_id.id')
        return {
            'name': _('Credit Notes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'in_refund'),
                ('invoice_line_ids.work_order_line_id', 'in', serial_ids),
                ('bill_type', '=', 'contractor'),
            ],
            'context': {'create': False},
            'target': 'current',
        }


    def action_post(self):
        """Final check before posting - backup validation"""
        for move in self:
            if move.move_type == 'in_invoice' and move.bill_type == 'contractor':
                self._check_contractor_duplicate_serials(move)
        return super(AccountMove, self).action_post()

    def _check_contractor_duplicate_serials(self, move):
        """Validate no duplicate serials (backup check before posting)"""
        serial_lines = move.invoice_line_ids.filtered(
            lambda l: l.work_order_line_id and l.display_type not in ('line_section', 'line_note')
        )

        if not serial_lines:
            return

        # Check for duplicates within same bill
        seen_serial_ids = set()
        for line in serial_lines:
            if line.work_order_line_id.id in seen_serial_ids:
                raise ValidationError(_(
                    "Serial No [%s] appears multiple times in this bill."
                ) % (line.work_order_line_id.wo_ser_product_display))
            seen_serial_ids.add(line.work_order_line_id.id)

        # Check for already billed serials
        for line in serial_lines:
            self._validate_serial_availability(line.work_order_line_id)

    def _validate_serial_availability(self, work_order_line):
        """Check if serial number is already billed without credit note.

        Billable ceiling = delivered_qty (when > 0) else product_qty.
        This prevents billing beyond what has been physically delivered.
        """
        if not work_order_line:
            return

        # Search for existing posted bills (excluding the current move)
        existing_bills = self.env['account.move.line'].search([
            ('work_order_line_id', '=', work_order_line.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'in_invoice'),
            ('move_id.bill_type', '=', 'contractor'),
            ('move_id', '!=', self.id),
        ])

        credit_notes = self.env['account.move.line'].search([
            ('work_order_line_id', '=', work_order_line.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'in_refund'),
            ('move_id.bill_type', '=', 'contractor'),
            ('move_id', '!=', self.id),
        ])

        # Calculate net billed quantity
        billed_qty = sum(
            line.ser_no_qty if line.ser_no_qty else line.quantity
            for line in existing_bills
        )
        credit_qty = sum(
            line.ser_no_qty if line.ser_no_qty else line.quantity
            for line in credit_notes
        )
        net_already_billed = billed_qty - credit_qty

        current_billed = sum(
            line.ser_no_qty if line.ser_no_qty else line.quantity
            for line in self.invoice_line_ids if line.work_order_line_id.id == work_order_line.id
        )

        total_qty = work_order_line.product_qty
        delivered_qty = work_order_line.delivered_qty or 0.0

        # Bill for what has NOT been delivered yet (remaining undelivered qty)
        # e.g. Total=6, Delivered=2  →  billable_ceiling=4
        billable_ceiling = max(0.0, total_qty - delivered_qty)

        if round(net_already_billed + current_billed, 3) > round(billable_ceiling, 3):
            if round(net_already_billed, 3) >= round(billable_ceiling, 3):
                latest_bill = existing_bills[0].move_id if existing_bills else self
                raise UserError(_(
                    "Product/Serial [%s] is already fully billed!\n\n"
                    "Previously billed in: %s\n"
                    "Billed: %s / Remaining (undelivered): %s\n"
                    "Please create a credit note for bill %s first before "
                    "using this product/serial again."
                ) % (
                    work_order_line.wo_ser_product_display,
                    latest_bill.name,
                    net_already_billed,
                    billable_ceiling,
                    latest_bill.name
                ))
            else:
                raise UserError(_(
                    "Cannot bill [%s] for quantity %s.\n\n"
                    "Only %s remaining to be billed out of %s undelivered total."
                ) % (
                    work_order_line.wo_ser_product_display,
                    current_billed,
                    billable_ceiling - net_already_billed,
                    billable_ceiling
                ))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    work_order_line_id = fields.Many2one(
        'work.order.line', 
        string="Serial No",
        copy=True
    )
    image_1 = fields.Binary(
        related='work_order_line_id.image_1', 
        string="Image 1", 
        readonly=True,
        store=False
    )
    image_2 = fields.Binary(
        related='work_order_line_id.image_2', 
        string="Image 2", 
        readonly=True,
        store=False
    )
    ser_no_qty = fields.Float(
        string="Serial No Qty",
        default=1.0,
        copy=True
    )

    @api.onchange('work_order_line_id')
    def _onchange_work_order_line_id(self):
        """
        Real-time validation when serial number is selected.
        Shows error immediately without saving.
        """
        if self.work_order_line_id and self.move_id.bill_type == 'contractor':

            serial_display = self.work_order_line_id.wo_ser_product_display
            line = self.work_order_line_id

            # ── Condition: status_item == 'cancelled' ────────────────────────────
            # Although the XML domain filters these out, guard defensively here too.
            if line.status_item == 'cancelled':
                self.work_order_line_id = False
                return {
                    'warning': {
                        'title': _('Product Cancelled'),
                        'message': _(
                            'Product: %s\n'
                            'This item has been cancelled and cannot be billed.'
                        ) % serial_display
                    }
                }

            # ── Remaining undelivered qty is what can be billed ──────────────────
            # e.g. Total=6, Delivered=2  →  billable_ceiling=4 (what contractor still owes)
            total_qty = line.product_qty
            delivered_qty = line.delivered_qty or 0.0

            # REAL-TIME CHECK: Calculate already billed from posted invoices
            existing_bills = self.env['account.move.line'].search([
                ('work_order_line_id', '=', line.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.bill_type', '=', 'contractor'),
            ])

            credit_notes = self.env['account.move.line'].search([
                ('work_order_line_id', '=', line.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_refund'),
                ('move_id.bill_type', '=', 'contractor'),
            ])

            billed_qty = sum(
                l.ser_no_qty if l.ser_no_qty else l.quantity
                for l in existing_bills
            )
            credit_qty = sum(
                l.ser_no_qty if l.ser_no_qty else l.quantity
                for l in credit_notes
            )
            net_already_billed = billed_qty - credit_qty

            # Billable ceiling = total - delivered (items not yet physically delivered)
            billable_ceiling = max(0.0, total_qty - delivered_qty)
            # What is still available to bill on this new bill
            remaining = max(0.0, billable_ceiling - net_already_billed)

            # ── Block: ceiling already exhausted by previous bills ────────────────
            if round(net_already_billed, 3) >= round(billable_ceiling, 3):
                if existing_bills:
                    latest_bill = existing_bills[0].move_id
                    msg = _(
                        'Product: %s\n'
                        'Already fully billed in: %s\n'
                        'Billed Quantity: %s / Remaining (undelivered): %s\n'
                        'Please create a credit note for bill %s first before '
                        'billing this product again.'
                    ) % (
                        serial_display,
                        latest_bill.name,
                        net_already_billed,
                        billable_ceiling,
                        latest_bill.name,
                    )
                else:
                    msg = _(
                        'Product: %s\n'
                        'No remaining undelivered quantity to bill.\n'
                        'Total: %s  |  Delivered: %s  |  Remaining to bill: %s'
                    ) % (serial_display, total_qty, delivered_qty, billable_ceiling)

                self.work_order_line_id = False
                return {
                    'warning': {
                        'title': _('Nothing Left to Bill – Create Credit Note First'),
                        'message': msg
                    }
                }

            # ── Duplicate within same bill ────────────────────────────────────────
            if self.move_id and self.move_id.invoice_line_ids:
                duplicate_in_bill = self.move_id.invoice_line_ids.filtered(
                    lambda l: l.work_order_line_id.id == self.work_order_line_id.id
                    and l.id != self.id
                    and l.id  # Exclude unsaved new records
                )

                if duplicate_in_bill:
                    self.work_order_line_id = False
                    return {
                        'warning': {
                            'title': _('Duplicate Product Selection!'),
                            'message': _(
                                'Product: %s\n'
                                'This product is already selected in another line of this bill.\n'
                                'Consider increasing the quantity on the existing line instead.\n'
                                'The product has been removed from this line.'
                            ) % (self.work_order_line_id.wo_ser_product_display if self.work_order_line_id else '')
                        }
                    }

            # Set qty to the remaining billable amount
            self.ser_no_qty = remaining
            if self.move_id.bill_type == 'contractor':
                self.quantity = self.ser_no_qty

    @api.onchange('ser_no_qty')
    def _onchange_ser_no_qty(self):
        """Keep quantity in sync with Serial No Qty for contractor bills and check limits"""
        if self.move_id.bill_type == 'contractor' and self.work_order_line_id:
            if self.ser_no_qty:
                self.quantity = self.ser_no_qty

            # Real-time check if quantity exceeds remaining
            move_origin_id = self.move_id._origin.id if getattr(self.move_id, '_origin', False) else self.move_id.id
            existing_bills = self.env['account.move.line'].search([
                ('work_order_line_id', '=', self.work_order_line_id.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.bill_type', '=', 'contractor'),
                ('move_id', '!=', move_origin_id),
            ])
            credit_notes = self.env['account.move.line'].search([
                ('work_order_line_id', '=', self.work_order_line_id.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_refund'),
                ('move_id.bill_type', '=', 'contractor'),
                ('move_id', '!=', move_origin_id),
            ])

            billed_qty = sum(
                line.ser_no_qty if line.ser_no_qty else line.quantity
                for line in existing_bills
            )
            credit_qty = sum(
                line.ser_no_qty if line.ser_no_qty else line.quantity
                for line in credit_notes
            )
            net_already_billed = billed_qty - credit_qty
            total_qty = self.work_order_line_id.product_qty
            delivered_qty = self.work_order_line_id.delivered_qty or 0.0
            # Bill for what has NOT been delivered yet (total - delivered)
            billable_ceiling = max(0.0, total_qty - delivered_qty)
            remaining = max(0.0, billable_ceiling - net_already_billed)

            if round(self.ser_no_qty, 3) > round(remaining, 3):
                # Build a helpful message: if there are posted bills, tell user to credit-note first
                if existing_bills and round(net_already_billed, 3) > 0:
                    latest_bill = existing_bills[0].move_id
                    msg = _(
                        'Quantity %s exceeds the remaining billable amount (%s) for [%s].\n\n'
                        'Already billed: %s out of %s delivered/total.\n'
                        'To bill more, please first create a Credit Note for bill %s '
                        'to free up capacity, then proceed.'
                    ) % (
                        self.ser_no_qty,
                        remaining,
                        self.work_order_line_id.wo_ser_product_display,
                        net_already_billed,
                        billable_ceiling,
                        latest_bill.name,
                    )
                else:
                    msg = _(
                        'Quantity %s exceeds the remaining allowed (%s) for [%s].\n'
                        'Maximum billable quantity is %s.'
                    ) % (
                        self.ser_no_qty,
                        remaining,
                        self.work_order_line_id.wo_ser_product_display,
                        billable_ceiling,
                    )
                self.ser_no_qty = remaining
                self.quantity = remaining
                return {
                    'warning': {
                        'title': _('Quantity Exceeded – Credit Note Required'),
                        'message': msg
                    }
                }

    @api.constrains('ser_no_qty', 'work_order_line_id')
    def _check_ser_no_qty(self):
        """Validate Serial No Qty is positive and doesn't exceed allowed total.
        
        Only applies to invoices (in_invoice), NOT to credit notes (in_refund).
        Credit notes must be allowed to copy the original billed quantities freely.
        """
        for line in self:
            if (
                line.move_id.bill_type == 'contractor'
                and line.move_id.move_type == 'in_invoice'  # skip credit notes
                and line.work_order_line_id
            ):
                if line.ser_no_qty <= 0:
                    raise ValidationError(_(
                        "Serial No Qty must be greater than 0 for %s"
                    ) % line.work_order_line_id.wo_ser_product_display)

                existing_bills = self.env['account.move.line'].search([
                    ('work_order_line_id', '=', line.work_order_line_id.id),
                    ('move_id.state', '=', 'posted'),
                    ('move_id.move_type', '=', 'in_invoice'),
                    ('move_id.bill_type', '=', 'contractor'),
                    ('move_id', '!=', line.move_id.id),
                ])
                credit_notes = self.env['account.move.line'].search([
                    ('work_order_line_id', '=', line.work_order_line_id.id),
                    ('move_id.state', '=', 'posted'),
                    ('move_id.move_type', '=', 'in_refund'),
                    ('move_id.bill_type', '=', 'contractor'),
                    ('move_id', '!=', line.move_id.id),
                ])
                billed_qty = sum(
                    l.ser_no_qty if l.ser_no_qty else l.quantity
                    for l in existing_bills
                )
                credit_qty = sum(
                    l.ser_no_qty if l.ser_no_qty else l.quantity
                    for l in credit_notes
                )
                net_already_billed = billed_qty - credit_qty

                total_qty = line.work_order_line_id.product_qty
                delivered_qty = line.work_order_line_id.delivered_qty or 0.0
                # Bill for what has NOT been delivered yet (total - delivered)
                billable_ceiling = max(0.0, total_qty - delivered_qty)

                if round(net_already_billed + line.ser_no_qty, 3) > round(billable_ceiling, 3):
                    raise ValidationError(_(
                        "Cannot bill [%s] for quantity %s.\n\n"
                        "Only %s remaining to be billed out of %s undelivered total."
                    ) % (
                        line.work_order_line_id.wo_ser_product_display,
                        line.ser_no_qty,
                        billable_ceiling - net_already_billed,
                        billable_ceiling
                    ))

    @api.constrains('work_order_line_id')
    def _check_work_order_line_unique_in_draft(self):
        """
        Additional validation layer for draft bills.
        Prevents saving duplicates even if onchange warning is bypassed.
        Only applies to invoices (in_invoice), NOT to credit notes (in_refund).
        """
        for line in self:
            if (
                line.work_order_line_id
                and line.move_id.bill_type == 'contractor'
                and line.move_id.move_type == 'in_invoice'  # skip credit notes
                and line.move_id.state == 'draft'
            ):
                # Check duplicates in same bill
                duplicate = self.env['account.move.line'].search([
                    ('work_order_line_id', '=', line.work_order_line_id.id),
                    ('move_id', '=', line.move_id.id),
                    ('id', '!=', line.id),
                ], limit=1)

                if duplicate:
                    raise ValidationError(_(
                        "Serial No [%s] is already used in this bill. "
                        "Each serial number can only appear once per bill."
                    ) % line.work_order_line_id.wo_ser_product_display)