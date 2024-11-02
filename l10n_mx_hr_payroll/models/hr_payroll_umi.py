from odoo import fields, models


class HrPayrollUmi(models.Model):
    _name = "hr.payroll.umi"
    _description = "Payroll UMI Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    date = fields.Date(required=True, index=True, default=fields.Date.context_today)
    amount = fields.Float(string="UMI Value")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
