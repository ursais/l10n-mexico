import logging

from pytz import timezone

from odoo import fields, models

_logger = logging.getLogger(__name__)
tzmx = timezone("America/Mexico_City")


class HrPayrollExtraTimeLine(models.Model):
    _name = "hr.payroll.extratime.line"
    _description = "Payroll Extratime line"
    _rec_name = "line_id"

    line_id = fields.Many2one(
        "hr.payroll.extratime",
        string="Extratime Reference",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
    )
    employee_id = fields.Many2one(
        related="line_id.employee_id", string="Employee", required=True
    )
    contract_id = fields.Many2one(
        related="line_id.contract_id", string="Contract", required=True
    )
    period_line_id = fields.Many2one(related="line_id.period_line_id", string="Period")
    date = fields.Date()
    hours = fields.Float()
    type_hour = fields.Selection(
        [
            ("double", "Double"),
            ("triple", "Triple"),
        ],
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )
