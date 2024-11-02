from random import randint

from odoo import fields, models


class HrPayrollRestDay(models.Model):
    _name = "hr.contract.restday"
    _description = "Payroll Rest Days"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(required=True)
    sequence = fields.Integer()
    color = fields.Integer(default=_get_default_color)
    contract_ids = fields.Many2many(
        "hr.contract",
        "contract_restday_rel",
        "restday_id",
        "contract_id",
    )

    _sql_constraints = [
        ("name_uniq", "unique (name)", "Rest day already exists!"),
    ]
