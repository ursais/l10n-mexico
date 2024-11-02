from odoo import fields, models


class HrPayrollUma(models.Model):
    _name = "hr.payroll.uma"
    _description = "Payroll UMA Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    date = fields.Date(required=True, index=True, default=fields.Date.context_today)
    daily = fields.Float()
    monthly = fields.Float()
    yearly = fields.Float()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
