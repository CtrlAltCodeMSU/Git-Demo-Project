from odoo import models, fields

class ProductStandardPriceHistory(models.Model):
    _name = 'product.standard.price.history'
    _description = 'Product Standard Price History'
    _order = 'date desc, id desc'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template', required=True, ondelete='cascade')
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    old_price = fields.Float(string='Old Price', digits='Product Price')
    new_price = fields.Float(string='New Price', digits='Product Price', required=True)
    user_id = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)
