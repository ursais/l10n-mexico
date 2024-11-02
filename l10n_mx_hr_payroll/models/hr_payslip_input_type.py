from odoo import fields, models


class HrPayslipInputType(models.Model):
    _inherit = "hr.payslip.input.type"
    _description = "Payslip Input Type"

    input_type_mx = fields.Selection(
        [
            ("loan", "Loan"),
            ("extratime", "Extratime"),
            ("movement", "Movement"),
            ("alimony", "Alimony"),
            ("ptu", "PTU"),
            ("bonus", "Bonus"),
        ],
        string="Rule Type",
        help="Rule Type",
    )
