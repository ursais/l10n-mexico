from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    type_use = fields.Selection(
        [
            ("payroll", "Payroll"),
            ("settlements", "Settlements/Liquidations"),
            ("bonus", "Bonus"),
            ("ptu", "Workers' profit sharing (PTU)"),
            ("others", "Others"),
        ],
        string="Use type",
        default="payroll",
        required=True,
    )
