from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    project_delivered = fields.Boolean(string="Project Delivered", default=False, tracking=True)
