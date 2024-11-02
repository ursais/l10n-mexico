from odoo import fields, models


class OtherPayments(models.Model):
    _name = "payroll.otherpayment"
    _rec_name = "description"
    _description = "Others Payments"

    code = fields.Char()
    description = fields.Char()
