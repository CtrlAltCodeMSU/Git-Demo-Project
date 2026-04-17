from odoo import api, models, fields
from odoo.exceptions import ValidationError


class WorkOrder(models.Model):
    _inherit = 'work.order'
    
    category = fields.Char(string="Category")
    total_items_qty = fields.Float(string="Total Items Qty", compute="_compute_total_items_qty")
    total_delivered_qty = fields.Float(string="Total Delivered Qty", compute="_compute_total_delivered_qty")
    
    
    @api.depends('work_order_line_ids', 'work_order_line_ids.product_qty')
    def _compute_total_items_qty(self):
        for record in self:
            total = sum(line.product_qty for line in record.work_order_line_ids if not line.display_type or line.display_type == 'line')
            record.total_items_qty = total

    @api.depends('work_order_line_ids','work_order_line_ids.delivered_qty')
    def _compute_total_delivered_qty(self):
        for record in self:
            total = sum(line.delivered_qty for line in record.work_order_line_ids if not line.display_type or line.display_type == 'line')
            record.total_delivered_qty = total

            
    # @api.depends('work_order_line_ids','work_order_line_ids.delivered_qty')
    # def _compute_total_delivered_qty(self):
    #     for record in self:
    #         total=sum(line.delivered_qty for line in record.work_order_line_ids if line.display_type == 'line')
    #         record.total_delivered_qty = total
    def write(self, vals):
        res = super(WorkOrder, self).write(vals)
        if vals.get('state') == 'delivered':
            for line in self.work_order_line_ids:
                if line.display_type in ('line', False):
                    line_vals = {}
                    if not line.delivery_date:
                        line_vals['delivery_date'] = fields.Date.today()
                    if line.department_status not in ['delivered', 'partially_delivered']:
                        line_vals['department_status'] = 'delivered'
                    if line.delivered_qty == 0:
                        line_vals['delivered_qty'] = line.product_qty
                    if line_vals:
                        line.write(line_vals)
        return res

    def _compute_display_name(self):
        super()._compute_display_name()
        if self._context.get('show_project_name'):
            for record in self:
                name = record.display_name or record.name or ''
                if record.project_id:
                    name = f"{name} - {record.project_id.name}"
                record.display_name = name


class WorkOrderLine(models.Model):
    _inherit = 'work.order.line'
    _rec_name = 'wo_ser_product_display'

    delivered_qty = fields.Float(string="Delivered Qty")
    fabric_description = fields.Char(string="Fabric Description")
    wo_ser_product_display = fields.Char(string="WO-Serial-Product", compute="_compute_wo_ser_product_display", store=False)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._format_wo_serial_product()

    @api.depends('work_order_id.name', 'ser_no', 'ser_no_s', 'product_id.name')
    def _compute_wo_ser_product_display(self):
        for rec in self:
            rec.wo_ser_product_display = rec._format_wo_serial_product()

    @api.depends('work_order_id.name', 'ser_no', 'ser_no_s', 'product_id.name')
    def _compute_display_name_custom(self):
        """Override base display_name_custom to keep Serial No label consistent."""
        for rec in self:
            rec.display_name_custom = rec._format_wo_serial_product()

    def _format_wo_serial_product(self):
        self.ensure_one()
        # Normalize WO name: "WO-00004" or "WO/00004" -> "WO00004"
        wo_raw = self.work_order_id.name or ''
        wo_number = wo_raw.replace('-', '').replace('/', '')

        # Prefer numeric serial if available, else parse ser_no_s
        serial_no = ''
        if self.ser_no:
            serial_no = str(self.ser_no)
        elif self.ser_no_s:
            # Handle formats like "WO-00004-S00001-1-Bed" -> extract '1'
            # Or "S00001-1" -> extract '1'
            parts = self.ser_no_s.split('-')
            candidate = parts[-1]
            if candidate.isdigit():
                serial_no = candidate
            else:
                # Fallback: find the first numeric part from the right that looks like a sub-serial
                for part in reversed(parts):
                    if part.isdigit():
                        serial_no = part
                        break
                if not serial_no:
                    digits = ''.join(ch for ch in self.ser_no_s if ch.isdigit())
                    serial_no = digits.lstrip('0') or digits

        product_name = self.product_id.name or ''

        # Format: WO00004-1-Bed
        parts = [p for p in [wo_number, serial_no, product_name] if p]
        return '-'.join(parts)

    def name_get(self):
        result = []
        for rec in self:
            # Always compute on the fly to avoid stale stored display values
            name = rec._format_wo_serial_product()
            result.append((rec.id, name))
        return result
    @api.constrains('delivered_qty', 'product_qty')
    def _check_delivered_qty(self):
        for line in self:
            if line.delivered_qty > line.product_qty:
                raise ValidationError("Delivered Quantity cannot be more than the total quantity.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('department_status') in ['delivered', 'partially_delivered'] and not vals.get('delivery_date'):
                vals['delivery_date'] = fields.Date.today()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('department_status') in ['delivered', 'partially_delivered'] and not vals.get('delivery_date'):
            vals['delivery_date'] = fields.Date.today()
        res = super().write(vals)

        # ── Sync cancellation back to Sale Order ──────────────────────────────
        # When status_item is set to 'cancelled' on a WO line, reflect it in
        # the linked Sale Order's "Cancelled Items" tab.
        if vals.get('status_item') == 'cancelled':
            CancelledLine = self.env['sale.order.cancelled.line']
            for wl in self:
                if not wl.product_id:
                    continue

                # Find the linked SO line (created-from-sale or imported)
                so_line = wl.source_sale_line_id or wl.sale_line_id
                if not so_line:
                    continue

                sale_order = so_line.order_id
                if not sale_order:
                    continue

                # Avoid creating a duplicate cancelled line for the same SO line
                already_exists = CancelledLine.search([
                    ('order_id', '=', sale_order.id),
                    ('product_id', '=', wl.product_id.id),
                    ('ser_no', '=', so_line.ser_no),
                ], limit=1)
                if already_exists:
                    continue

                # Create the cancelled line on the Sale Order
                CancelledLine.create({
                    'order_id': sale_order.id,
                    'product_id': wl.product_id.id,
                    'ser_no': so_line.ser_no or wl.ser_no or 0,
                    'image_1': wl.image_1 or so_line.image_1 or False,
                    'image_2': wl.image_2 or so_line.image_2 or False,
                    'quantity': wl.product_qty,
                    'uom_id': so_line.product_uom.id if so_line.product_uom else False,
                    'price_unit': so_line.price_unit,
                    'tax_id': [(6, 0, so_line.tax_id.ids)],
                    'total': so_line.price_subtotal,
                    'status': 'cancelled',
                })

                # Also mark the SO line itself as cancelled and hide it,
                # mirroring what happens when done from the SO side.
                if so_line.status != 'cancelled':
                    so_line.with_context(skip_wo_sync=True).write({
                        'status': 'cancelled',
                        'active': False,
                    })

        return res

    @api.onchange('department_status')
    def _onchange_department_status_delivery_date(self):
        for rec in self:
            if rec.department_status in ['delivered', 'partially_delivered'] and not rec.delivery_date:
                rec.delivery_date = fields.Date.today()
            if rec.department_status == 'delivered' and rec.delivered_qty == 0:
                rec.delivered_qty = rec.product_qty
            if rec.department_status == 'partially_delivered' and rec.delivered_qty == 0:
                raise ValidationError("Please enter Delivered Quantity for Partially Delivered status.")
                # rec.delivered_qty = rec.product_qty / 2
