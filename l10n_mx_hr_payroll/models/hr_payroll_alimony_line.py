from odoo import fields, models


class HrPayrollAlimonyLine(models.Model):
    _name = "hr.payroll.alimony.line"
    _description = "Payroll Alimony Line"

    line_id = fields.Many2one("hr.payroll.alimony", required=True, ondelete="cascade")
    name = fields.Many2one("hr.employee")
    payslip_id = fields.Many2one("hr.payslip")
    date = fields.Date()
    amount = fields.Float()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("paid", "Paid"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )
