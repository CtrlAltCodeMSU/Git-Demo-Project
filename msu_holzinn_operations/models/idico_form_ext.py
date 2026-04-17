from odoo import models, fields, api

class IdicoForm(models.Model):
    _inherit = 'idico.form'
    _order = 'confirmation_date desc, creation_date desc, id desc'

    is_fabric_completed = fields.Boolean(string="Fabric Completed", tracking=True)
    confirmation_date = fields.Datetime(
        string="Confirmation Date",
        compute='_compute_confirmation_date',
        store=True,
        tracking=True
    )

    @api.depends('state')
    def _compute_confirmation_date(self):
        for rec in self:
            if rec.state == 'confirm' and not rec.confirmation_date:
                real_id = rec._origin.id if rec._origin else rec.id
                if not real_id:
                    rec.confirmation_date = fields.Datetime.now()
                    continue

                trackings = self.env['mail.tracking.value'].search([
                    ('mail_message_id.model', '=', 'idico.form'),
                    ('mail_message_id.res_id', '=', real_id),
                    ('field_id.name', '=', 'state')
                ], order='id desc')
                
                # The latest tracking on 'state' that resulted in 'confirm' provides our date
                if trackings:
                    rec.confirmation_date = trackings[0].mail_message_id.date
                else:
                    rec.confirmation_date = rec.write_date or fields.Datetime.now()
            elif rec.state != 'confirm':
                rec.confirmation_date = False



class IdicoFormLine(models.Model):
    _inherit = 'idico.form.line'
    _order = 'sequence, id'

    line_description = fields.Char(
        string="Description",
        related='work_id.fabric_description',
        store=True,
        readonly=False
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Customer",
        related='idico_form_id.partner_id',
        store=True,
        readonly=True
    )