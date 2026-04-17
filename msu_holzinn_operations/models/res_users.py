# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    idle_timeout = fields.Selection([
        ('15', '15 Minutes'),
        ('25', '25 Minutes'),
        ('35', '35 Minutes'),
        ('40', '40 Minutes'),
        ('45', '45 Minutes'),
        ('custom', 'Custom Time'),
        ('never', 'Never'),
    ], string="Idle Timeout", default='never',
       help="Automatic logout after this period of inactivity.")

    custom_idle_timeout = fields.Integer(
        string="Custom Timeout (Minutes)",
        default=0,
        help="Specify timeout in minutes."
    )

    @api.constrains('custom_idle_timeout')
    def _check_custom_idle_timeout(self):
        for record in self:
            if record.idle_timeout == 'custom' and record.custom_idle_timeout <= 0:
                raise models.ValidationError(
                    "Custom timeout must be greater than 0 minutes."
                )