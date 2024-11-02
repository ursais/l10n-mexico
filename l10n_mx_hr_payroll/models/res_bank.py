import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HrResBank(models.Model):
    _inherit = "res.bank"

    hr_payroll_template_dispersion = fields.Many2one(
        comodel_name="ir.ui.view", string="Bank Template"
    )
