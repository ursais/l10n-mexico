from odoo import api, fields, models


class HrPayrollPeriodLine(models.Model):
    _name = "hr.payroll.period.line"
    _description = "Payroll Period Line"
    _order = "sequence"

    period_id = fields.Many2one(
        "hr.payroll.period", string="Period", required=True, ondelete="cascade"
    )
    sequence = fields.Integer()
    name = fields.Char(required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    date_pay = fields.Date(string="Date of pay")
    days = fields.Integer(compute="_compute_days")
    state = fields.Selection(
        [
            ("open", "Open"),
            ("closed", "Closed"),
        ],
        default="open",
        help="""* """,
    )

    @api.depends("date_start", "date_end")
    def _compute_days(self):
        for period in self:
            if period.date_end and period.date_start:
                de = fields.Datetime.from_string(period.date_end)
                ds = fields.Datetime.from_string(period.date_start)
                period.days = (de - ds).days + 1
            else:
                period.days = 0
