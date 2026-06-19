# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MOCK_CER = base64.b64encode(b"fake-cer-content")
MOCK_KEY = base64.b64encode(b"fake-key-content")
MOCK_PASSWORD = "test-password"

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"


@tagged("post_install", "-at_install")
class TestResConfigSettingsSAT(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "country_id": cls.env.ref("base.mx").id,
                "vat": "EKU9003173C9",
            }
        )

    def test_settings_proxy_test_connection(self):
        settings = self.env["res.config.settings"].create(
            {
                "company_id": self.company.id,
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with patch(f"{_SVC}.SAT") as mock_sat_cls, patch(f"{_SVC}.Signer.load") as mock_signer:
            mock_signer.return_value.rfc = self.company.vat
            mock_sat_cls.return_value._autentica_comprobante.return_value = {
                "AutenticaResult": "fake-token"
            }
            result = settings.l10n_mx_sat_test_connection()
        self.assertEqual(result["params"]["type"], "success")
