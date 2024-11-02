from odoo import fields, models


class HrPayrollIsrLine(models.Model):
    _name = "hr.payroll.isr.line"
    _description = "Payroll ISR Table - Line"

    line_id = fields.Many2one(
        "hr.payroll.isr", string="Period", required=True, ondelete="cascade"
    )
    name = fields.Integer(string="Sequence")
    lim_inf = fields.Float(string="Inferior limit")
    lim_sup = fields.Float(string="Superior limit")
    fix_fee = fields.Float(string="Fix fee")
    percent = fields.Float()
