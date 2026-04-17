from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()

        # Set  custom field vendor bill type to 'vendor' for purchase orders
        vals['bill_type'] = 'vendor'

        return vals