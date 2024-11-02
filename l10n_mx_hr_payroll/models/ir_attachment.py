import logging

from odoo import api, models, tools

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def l10n_mx_hr_payroll_edi_validate_xml_from_attachment(
        self, xml_content, xsd_name
    ):
        tools.validate_xml_from_attachment(
            self.env, xml_content, xsd_name, prefix="l10n_mx_hr_payroll_edi"
        )
