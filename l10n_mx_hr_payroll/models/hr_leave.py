import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    hr_leave_id = fields.Many2one("hr.leave")


class HolidaysType(models.Model):
    _inherit = "hr.leave"

    disability_folio = fields.Char()
    is_disability = fields.Boolean(compute="_compute_is_disability")

    @api.depends("holiday_status_id")
    def _compute_is_disability(self):
        for disability in self:
            if disability.holiday_status_id.disabilities_type:
                disability.is_disability = True
            else:
                disability.is_disability = False
