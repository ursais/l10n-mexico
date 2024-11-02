from odoo import fields, models


class HrPayrollPc(models.Model):
    _name = "hr.payroll.pc"
    _description = "Payroll Performance Catalog"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many("hr.payroll.pc.line", "line_id", string="Lines")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
