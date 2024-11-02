from odoo import fields, models


# Payroll Period table
class HrPayrollPeriod(models.Model):
    _name = "hr.payroll.period"
    _description = "Payroll Period"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    type_id = fields.Many2one("hr.payroll.period.type", required=True)
    structure_id = fields.Many2one("hr.payroll.structure", string="Payroll Structure")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    note = fields.Text(string="Description")
    line_ids = fields.One2many(
        "hr.payroll.period.line", "period_id", string="Periods Lines"
    )
