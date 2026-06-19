# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Kept on res.config.settings for backward compatibility with existing
    # inherited settings views in the database and third-party modules.
    l10n_mx_sat_fiel_cer = fields.Binary(
        related="company_id.l10n_mx_sat_fiel_cer",
        readonly=False,
    )
    l10n_mx_sat_fiel_key = fields.Binary(
        related="company_id.l10n_mx_sat_fiel_key",
        readonly=False,
    )
    l10n_mx_sat_fiel_password = fields.Char(
        related="company_id.l10n_mx_sat_fiel_password",
        readonly=False,
    )
    l10n_mx_sat_sync_from = fields.Date(
        related="company_id.l10n_mx_sat_sync_from",
        readonly=False,
    )
    l10n_mx_sat_metadata_sync_from = fields.Date(
        related="company_id.l10n_mx_sat_metadata_sync_from",
        readonly=False,
    )
    l10n_mx_sat_last_sync = fields.Datetime(
        related="company_id.l10n_mx_sat_last_sync",
    )
    l10n_mx_sat_last_metadata_sync = fields.Datetime(
        related="company_id.l10n_mx_sat_last_metadata_sync",
    )
    l10n_mx_sat_auto_download = fields.Boolean(
        related="company_id.l10n_mx_sat_auto_download",
        readonly=False,
    )
    l10n_mx_sat_download_cfdi_issued = fields.Boolean(
        related="company_id.l10n_mx_sat_download_cfdi_issued",
        readonly=False,
    )
    l10n_mx_sat_download_cfdi_received = fields.Boolean(
        related="company_id.l10n_mx_sat_download_cfdi_received",
        readonly=False,
    )
    l10n_mx_sat_download_retention_issued = fields.Boolean(
        related="company_id.l10n_mx_sat_download_retention_issued",
        readonly=False,
    )
    l10n_mx_sat_download_retention_received = fields.Boolean(
        related="company_id.l10n_mx_sat_download_retention_received",
        readonly=False,
    )
    l10n_mx_sat_fiel_configured = fields.Boolean(
        related="company_id.l10n_mx_sat_fiel_configured",
    )
    l10n_mx_sat_fiel_rfc = fields.Char(
        related="company_id.l10n_mx_sat_fiel_rfc",
    )

    def l10n_mx_sat_test_connection(self):
        """Proxy for the 'Test connection' button in settings."""
        return self.company_id.l10n_mx_sat_test_connection()

    def l10n_mx_sat_sync_now(self):
        """Proxy for manual SAT sync from settings."""
        return self.company_id.l10n_mx_sat_sync_now()

    def l10n_mx_sat_open_fiel_wizard(self):
        """Proxy to open the FIEL credentials wizard from settings."""
        return self.company_id.action_l10n_mx_sat_open_fiel_wizard()
