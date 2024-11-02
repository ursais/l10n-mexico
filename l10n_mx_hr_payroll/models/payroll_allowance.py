from odoo import fields, models


class AllowanceType(models.Model):
    _name = "payroll.allowance"
    _rec_name = "description"
    _description = "Perception Type"

    code = fields.Char()
    description = fields.Char()
