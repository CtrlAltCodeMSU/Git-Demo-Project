from odoo import models, fields, api

class ProductTemplateExt(models.Model):
    _inherit = 'product.template'

    standard_price_date = fields.Date(string='Standard Price Date', readonly=True)
    price_history_ids = fields.One2many(
        'product.standard.price.history', 
        'product_tmpl_id', 
        string='Price History'
    )

    def write(self, vals):
        if self.env.context.get('skip_price_history'):
            return super(ProductTemplateExt, self).write(vals)
            
        old_prices = {rec.id: rec.standard_pri for rec in self}
        res = super(ProductTemplateExt, self).write(vals)
        
        for rec in self:
            if rec.standard_pri != old_prices.get(rec.id):
                self.env['product.standard.price.history'].create({
                    'product_tmpl_id': rec.id,
                    'old_price': old_prices.get(rec.id),
                    'new_price': rec.standard_pri,
                    'date': fields.Datetime.now(),
                    'user_id': self.env.user.id
                })
                rec.with_context(skip_price_history=True).write({
                    'standard_price_date': fields.Date.context_today(self)
                })
        return res
