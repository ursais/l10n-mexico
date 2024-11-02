from odoo import fields, models


class HrPayrollEsLine(models.Model):
    _name = "hr.payroll.es.line"
    _description = "Payroll Employment Subsidy Table - Line"

    line_id = fields.Many2one(
        "hr.payroll.es", string="Line", required=True, ondelete="cascade"
    )
    name = fields.Integer(string="Sequence")
    inf_sup = fields.Float(string="Inferior Limit")
    lim_sup = fields.Float(string="Superior Limit")
    fix_fee = fields.Float(string="Fix fee")
