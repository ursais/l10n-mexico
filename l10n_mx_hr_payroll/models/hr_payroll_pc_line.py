from odoo import fields, models


class HrPayrollPcLine(models.Model):
    _name = "hr.payroll.pc.line"
    _description = "Payroll Performance Catalog - Line"

    line_id = fields.Many2one("hr.payroll.pc", required=True, ondelete="cascade")
    name = fields.Integer(string="Sequence")
    antiquity = fields.Integer()
    holidays = fields.Float()
    pvp = fields.Float(string="Proportional vacation Premium")
    bonus = fields.Float()
    factor = fields.Float()
