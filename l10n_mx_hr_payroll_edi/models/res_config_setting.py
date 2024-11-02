from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # == PAC web-services ==
    l10n_mx_hr_payroll_edi_pac = fields.Selection(
        related="company_id.l10n_mx_hr_payroll_edi_pac",
        readonly=False,
        string="MX PAC* for Payroll",
    )
    l10n_mx_hr_payroll_edi_pac_test_env = fields.Boolean(
        related="company_id.l10n_mx_hr_payroll_edi_pac_test_env",
        readonly=False,
        string="MX PAC test environment* for Payroll",
    )
    l10n_mx_hr_payroll_edi_pac_username = fields.Char(
        related="company_id.l10n_mx_hr_payroll_edi_pac_username",
        readonly=False,
        string="MX PAC username* for Patroll",
    )
    l10n_mx_hr_payroll_edi_pac_password = fields.Char(
        related="company_id.l10n_mx_hr_payroll_edi_pac_password",
        readonly=False,
        string="MX PAC password* for payroll",
    )
    l10n_mx_hr_payroll_edi_certificate_ids = fields.Many2many(
        related="company_id.l10n_mx_hr_payroll_edi_certificate_ids",
        readonly=False,
        string="MX Certificates* for payroll",
    )

    l10n_mx_hr_payroll_mode2work = fields.Selection(
        related="company_id.l10n_mx_hr_payroll_mode2work",
        readonly=False,
        string="Payroll Work Method",
    )
