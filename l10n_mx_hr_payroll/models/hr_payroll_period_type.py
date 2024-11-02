from odoo import fields, models


class HrPayrollPeriodsType(models.Model):
    _name = "hr.payroll.period.type"
    _description = "Payroll Type of Period"

    code = fields.Char(required=True)
    name = fields.Char(string="Description", required=True)
    active = fields.Boolean(default=True)
    period_cfdi = fields.Selection(
        [
            ("01", "Daily"),
            ("02", "Weekly"),
            ("03", "Biweekly"),
            ("04", "Fortnightly"),
            ("05", "Monthly"),
            ("06", "Bimonthly"),
            ("07", "Work Unit"),
            ("08", "Commission"),
            ("09", "Fixed price"),
            ("10", "Decennial"),
            ("99", "Other Periodicity"),
        ],
        string="Payment Period",
        help="Payment Period",
    )
    payroll_type = fields.Selection(
        [("O", "Ordinary Payroll"), ("E", "Extraordinary Payroll")],
        string="Payroll type",
        help="Payroll type",
    )
