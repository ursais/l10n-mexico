from odoo import fields, models


class HrPayrollIsr(models.Model):
    _name = "hr.payroll.isr"
    _description = "Payroll ISR Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    type_table = fields.Selection(
        [
            ("d", "Daily"),
            ("w", "Weekly"),
            ("t", "Every 10 days"),
            ("b", "Biweekly"),
            ("m", "Monthly"),
            ("a", "Anually"),
        ],
        string="Type",
        help="""* """,
    )
    line_ids = fields.One2many("hr.payroll.isr.line", "line_id", string="Periods Lines")
