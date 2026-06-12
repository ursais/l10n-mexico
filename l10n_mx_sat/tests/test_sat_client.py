# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services import SatClient

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"


@tagged("post_install", "-at_install")
class TestSatClient(TransactionCase):
    """Tests for the SatClient adapter (pure Python class)."""

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_init_creates_signer_and_sat(self, mock_signer_load, mock_sat_cls):
        SatClient(b"cer", b"key", "pwd")
        mock_signer_load.assert_called_once_with(
            certificate=b"cer", key=b"key", password="pwd"
        )
        mock_sat_cls.assert_called_once()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_authenticate_returns_token(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "tok-123"
        }
        client = SatClient(b"cer", b"key", "pwd")

        token = client.authenticate()

        self.assertEqual(token, "tok-123")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_authenticate_empty_token_raises(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": ""
        }
        client = SatClient(b"cer", b"key", "pwd")

        with self.assertRaises(ValueError):
            client.authenticate()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-1",
            "Mensaje": "Aceptada",
        }
        client = SatClient(b"cer", b"key", "pwd")

        result = client.request_download(
            "tok", "RFC1", "2026-01-01", "2026-01-31"
        )

        self.assertEqual(
            result,
            {"cod_estatus": "5000", "id_solicitud": "SOL-1", "mensaje": "Aceptada"},
        )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_defaults_estado_comprobante(
        self, mock_signer_load, mock_sat_cls
    ):
        """estado_comprobante defaults to 'Vigente' for SAT CFDI downloads."""
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")

        client.request_download("tok", "RFC1", "2026-01-01", "2026-01-31")

        call_kwargs = (
            mock_sat_cls.return_value.recover_comprobante_received_request.call_args.kwargs
        )
        self.assertEqual(call_kwargs.get("estado_comprobante"), "Vigente")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_allows_override_estado(self, mock_signer_load, mock_sat_cls):
        """Caller can still override estado_comprobante if needed."""
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")

        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            estado_comprobante="Cancelado",
        )

        call_kwargs = (
            mock_sat_cls.return_value.recover_comprobante_received_request.call_args.kwargs
        )
        self.assertEqual(call_kwargs.get("estado_comprobante"), "Cancelado")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_verify_download(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_status.return_value = {
            "CodEstatus": "5000",
            "EstadoSolicitud": 3,
            "CodigoEstadoSolicitud": "5000",
            "NumeroCFDIs": 10,
            "IdsPaquetes": ["PKG-1"],
            "Mensaje": "Terminada",
        }
        client = SatClient(b"cer", b"key", "pwd")

        result = client.verify_download("tok", "RFC1", "SOL-1")

        self.assertEqual(
            result,
            {
                "cod_estatus": "5000",
                "estado_solicitud": 3,
                "codigo_estado_solicitud": "5000",
                "numero_cfdis": 10,
                "paquetes": ["PKG-1"],
                "mensaje": "Terminada",
            },
        )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_download_package(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_download.return_value = (
            {"CodEstatus": "5000", "Mensaje": "OK"},
            "b64data",
        )
        client = SatClient(b"cer", b"key", "pwd")

        result = client.download_package("tok", "RFC1", "PKG-1")

        self.assertEqual(
            result,
            {"cod_estatus": "5000", "paquete_b64": "b64data", "mensaje": "OK"},
        )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_validate_cfdi(self, mock_signer_load, mock_sat_cls):
        from lxml import etree

        consulta_result = etree.Element("ConsultaResult")
        etree.SubElement(consulta_result, "CodigoEstatus").text = "S - OK"
        etree.SubElement(consulta_result, "EsCancelable").text = (
            "Cancelable con aceptacion"
        )
        etree.SubElement(consulta_result, "Estado").text = "Vigente"
        consulta_response = etree.Element("ConsultaResponse")
        consulta_response.append(consulta_result)
        body = etree.Element("Body")
        body.append(consulta_response)
        envelope = etree.Element("Envelope")
        envelope.append(body)
        mock_sat_cls.return_value._request.return_value = envelope
        client = SatClient(b"cer", b"key", "pwd")

        result = client.validate_cfdi("RFC1", "RFC2", "100.00", "uuid-1")

        self.assertEqual(result["estado"], "Vigente")
        self.assertEqual(result["es_cancelable"], "Cancelable con aceptacion")
        self.assertEqual(result["codigo_estatus"], "S - OK")
