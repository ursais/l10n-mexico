from odoo import fields, models


class DeductionType(models.Model):
    _name = "payroll.deduction"
    _rec_name = "description"
    _description = "Deduction Type"

    code = fields.Char()
    description = fields.Char()
