from odoo import models, fields, api

class StockQuantExt(models.Model):
    _inherit = 'stock.quant'

    custom_system_qty = fields.Float(string="System Qty", readonly=True, help="System quantity at the time of adjustment")
    custom_counted_qty = fields.Float(string="Counted Qty", readonly=True, help="User counted quantity")
    custom_difference = fields.Float(string="Difference Qty", readonly=True, help="Difference between counted and system quantity")
    custom_adjustment_date = fields.Date(string="Adjustment Date", readonly=True, help="Date when the inventory was adjusted")

    def action_apply_inventory(self):
        # Save the fields before Odoo zeroes them out
        for quant in self:
            if quant.inventory_quantity_set:
                quant.custom_system_qty = quant.quantity
                quant.custom_counted_qty = quant.inventory_quantity
                quant.custom_difference = quant.inventory_diff_quantity
                quant.custom_adjustment_date = fields.Date.today()
        
        # Call super to actually apply the inventory
        return super(StockQuantExt, self).action_apply_inventory()
