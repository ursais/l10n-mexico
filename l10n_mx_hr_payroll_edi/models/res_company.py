import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # == PAC web-services ==
    l10n_mx_hr_payroll_edi_pac = fields.Selection(
        selection=[
            ("solfact", "Solución Factible"),
            ("facturalo", "Factúralo"),
            ("finkok", "Finkok"),
            ("sw", "SW sapien-SmarterWEB"),
            ("emaanu", "e-Maanu (Multipac)"),
        ],
        string="PAC for payroll",
        help="The PAC that will sign/cancel the invoices",
        default="emaanu",
    )
    l10n_mx_hr_payroll_edi_pac_test_env = fields.Boolean(
        string="PAC test environment for payroll",
        help="Enable the usage of test credentials",
        default=False,
    )
    l10n_mx_hr_payroll_edi_pac_username = fields.Char(
        string="PAC username for payroll",
        help="The username used to request the seal from the PAC",
        groups="base.group_system",
    )
    l10n_mx_hr_payroll_edi_pac_password = fields.Char(
        string="PAC password for payroll",
        help="The password used to request the seal from the PAC",
        groups="base.group_system,hr_payroll.group_hr_payroll_manager",
    )
    l10n_mx_hr_payroll_edi_certificate_ids = fields.Many2many(
        "l10n_mx_payroll_edi.certificate", string="Certificates (MX) for payroll"
    )

    l10n_mx_hr_payroll_mode2work = fields.Selection(
        selection=[
            ("stamp", "Stamp First and then create entries account"),
            ("same_time", "Stamp and create entries account at the same time"),
        ],
        string="Payroll Work Method",
        help="",
        default="stamp",
    )
