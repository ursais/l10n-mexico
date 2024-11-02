from odoo import fields, models


class HrPayrollTableES(models.Model):
    _name = "hr.payroll.es"
    _description = "Payroll Employement Subsidy Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    type_table = fields.Selection(
        [
            ("d", "Dialy"),
            ("w", "Weekly"),
            ("d", "Decenial"),
            ("b", "Biweekly"),
            ("m", "Monthly"),
            ("a", "Anual"),
        ],
        string="Type",
        help="""* """,
    )
    line_ids = fields.One2many("hr.payroll.es.line", "line_id", string="Periods Lines")
