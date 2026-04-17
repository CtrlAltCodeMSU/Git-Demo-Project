from odoo import api, models, fields
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    project_handover = fields.Boolean(string="Project Handover", copy=False)
    project_handover_date = fields.Date(string="Project Handover Date", copy=False)
    promised_date = fields.Date(string="Promised Date")
    category = fields.Char(string="Category")
    has_work_order = fields.Boolean(
        string="Has Work Order",
        compute="_compute_has_work_order",
        search="_search_has_work_order"
    )

    def _compute_has_work_order(self):
        for order in self:
            # Reusing the existing work_order_count logic
            order.has_work_order = order.work_order_count > 0

    def _search_has_work_order(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError("Only '=' and '!=' operators are supported for has_work_order")

        # Normalize the search to "HAS WORK ORDER"
        # If value is True and operator is '=', we want orders with WOs.
        # If value is False and operator is '=', we want orders without WOs.
        # If operator is '!=', we flip the value.
        target_has_wo = bool(value) if operator == '=' else not bool(value)

        # Search for all work orders and find their linked sale orders
        work_orders = self.env['work.order'].search([
            '|',
            ('sale_order_id', '!=', False),
            ('import_sale_order_ids', '!=', False)
        ])
        
        # Collect all linked sale order IDs
        so_ids = set()
        for wo in work_orders:
            if wo.sale_order_id:
                so_ids.add(wo.sale_order_id.id)
            if wo.import_sale_order_ids:
                so_ids.update(wo.import_sale_order_ids.ids)

        if target_has_wo:
            return [('id', 'in', list(so_ids))]
        else:
            return [('id', 'not in', list(so_ids))]

    
    total_items_qty = fields.Float(string="Total Items Qty", compute="_compute_total_items_qty")

    @api.depends(
        'order_line.product_uom_qty',
        'order_line.display_type',
        'order_line.name',
        'order_line.is_downpayment',
        'order_line.product_id',
    )
    def _compute_total_items_qty(self):
        for record in self:
            valid_lines = record.order_line.filtered(
                lambda l: (
                    not l.display_type
                    and not l.is_downpayment
                    and not (l.name and l.name.strip().lower().startswith('discount'))
                    and not (
                        l.product_id
                        and l.product_id.name
                        and l.product_id.name.strip().lower() == 'discount'
                    )
                )
            )
            record.total_items_qty = sum(line.product_uom_qty for line in valid_lines)

    @api.onchange('project_handover')
    def _onchange_project_handover(self):
        for record in self:
            if record.project_handover and not record.project_handover_date:
                record.project_handover_date = fields.Date.context_today(record)
                
    def action_confirm(self):
        for order in self:
            if not order.promised_date:
                raise ValidationError("You must set the Promised Date before confirming the order!")
        # Call super to continue the normal confirm process
        return super(SaleOrder, self).action_confirm()
