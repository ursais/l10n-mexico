# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrPayrollLoanLine(models.Model):
    _name = "hr.payroll.loan.line"
    _description = "Payroll Loan - Line"

    line_id = fields.Many2one("hr.payroll.loan", required=True, ondelete="cascade")
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
