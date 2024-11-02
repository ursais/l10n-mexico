import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HolidaysType(models.Model):
    _inherit = "hr.leave.type"

    disabilities_type = fields.Selection(
        [
            ("temporal_disability", "Temporal Disability"),
            ("temporal_partial_disability", "Temporal Partial Disability"),
            ("permanent_Disability", "Permanent Disability"),
        ],
        string="Disability Type",
    )
