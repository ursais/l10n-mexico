# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..services import SatClient

MOCK_CER = base64.b64encode(b"fake-cer-content")
MOCK_KEY = base64.b64encode(b"fake-key-content")
MOCK_PASSWORD = "test-password"

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"
_WIZ_SVC = (
    "odoo.addons.l10n_mx_sat.wizards.l10n_mx_sat_fiel_credentials_wizard.SatClient"
)


@tagged("post_install", "-at_install")
class TestResCompanySATConnection(TransactionCase):
    """Test res.company SAT methods (factory, auth, test connection)."""

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

    def _set_credentials(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )

    def test_missing_certificate_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_missing_key_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_missing_password_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": False,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_get_credentials_returns_decoded(self):
        self._set_credentials()
        cer, key, pwd = self.company.l10n_mx_sat_get_credentials()
        self.assertEqual(cer, b"fake-cer-content")
        self.assertEqual(key, b"fake-key-content")
        self.assertEqual(pwd, MOCK_PASSWORD)

    def test_invalid_base64_credentials_raise_user_error(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": b"abc",
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_client_returns_sat_client(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        client = self.company.l10n_mx_sat_get_client()
        self.assertIsInstance(client, SatClient)
        mock_signer_load.assert_called_once()
        mock_sat_cls.assert_called_once()

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_rfc_uses_company_vat(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.return_value.rfc = "RFCFIEL123"
        client = self.company.l10n_mx_sat_get_client()
        self.assertEqual(self.company.l10n_mx_sat_get_rfc(client), "EKU9003173C9")

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_rfc_falls_back_to_fiel(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        self.company.vat = False
        mock_signer_load.return_value.rfc = "RFCFIEL123"
        client = self.company.l10n_mx_sat_get_client()
        self.assertEqual(self.company.l10n_mx_sat_get_rfc(client), "RFCFIEL123")

    @patch("odoo.addons.l10n_mx_sat.models.res_company.SatClient")
    def test_get_client_exception_raises_user_error(self, MockSatClient):
        self._set_credentials()
        MockSatClient.side_effect = Exception("Invalid credentials")
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_client()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_get_token_returns_string(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "fake-token"
        }

        token = self.company.l10n_mx_sat_get_token()

        self.assertEqual(token, "fake-token")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_test_connection_success(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "fake-token"
        }

        result = self.company.l10n_mx_sat_test_connection()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")

    @mute_logger("odoo.addons.l10n_mx_sat.models.res_company")
    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_connection_exception_raises(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.side_effect = Exception(
            "Network error"
        )

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()

    @mute_logger("odoo.addons.l10n_mx_sat.models.res_company")
    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_empty_token_raises(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": ""
        }

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()

    def test_get_xml_download_flows_default_four(self):
        flows = self.company.l10n_mx_sat_get_xml_download_flows()
        self.assertEqual(
            flows,
            [
                ("cfdi", "issued", "xml"),
                ("cfdi", "received", "xml"),
                ("retention", "issued", "xml"),
                ("retention", "received", "xml"),
            ],
        )

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_fiel_configured_status(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        self.company.invalidate_recordset(
            [
                "l10n_mx_sat_fiel_configured",
                "l10n_mx_sat_fiel_certificate_configured",
                "l10n_mx_sat_fiel_key_configured",
                "l10n_mx_sat_fiel_rfc",
            ]
        )
        self.assertTrue(self.company.l10n_mx_sat_fiel_configured)
        self.assertTrue(self.company.l10n_mx_sat_fiel_certificate_configured)
        self.assertTrue(self.company.l10n_mx_sat_fiel_key_configured)
        self.assertEqual(self.company.l10n_mx_sat_fiel_rfc, self.company.vat)

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_fiel_wizard_updates_credentials(self, mock_sat_cls, mock_signer_load):
        mock_signer_load.return_value.rfc = "RFCFIEL123"
        self.company.vat = False
        with patch(_WIZ_SVC) as MockWizardClient:
            MockWizardClient.return_value.rfc = "RFCFIEL123"
            wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
                {
                    "company_id": self.company.id,
                    "fiel_cer": MOCK_CER,
                    "fiel_key": MOCK_KEY,
                    "fiel_password": MOCK_PASSWORD,
                }
            )
            wizard.action_apply()
        self.assertTrue(self.company.l10n_mx_sat_has_credentials())
        self.assertEqual(self.company.l10n_mx_sat_fiel_password, MOCK_PASSWORD)
        self.assertEqual(self.company.vat, "RFCFIEL123")
        self.assertNotEqual(self.company.l10n_mx_sat_fiel_cer, False)
        self.assertNotEqual(self.company.l10n_mx_sat_fiel_key, False)

    def test_vat_cannot_change_when_fiel_configured(self):
        self._set_credentials()
        with self.assertRaises(UserError):
            self.company.write({"vat": "AAA010101AAA"})
