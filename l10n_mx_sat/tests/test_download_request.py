# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime
from unittest.mock import MagicMock, patch

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_mx_sat.services import (
    SAT_CODE_DUPLICATE_LIFETIME,
    SAT_CODE_MAX_ELEMENTS,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_ESTADO_REJECTED,
)
from odoo.addons.l10n_mx_sat.services.sat_metadata import (
    build_request_fingerprint,
    normalize_sat_estado,
    parse_metadata_content,
)


@tagged("post_install", "-at_install")
class TestSatMetadata(TransactionCase):
    def test_normalize_sat_estado(self):
        self.assertEqual(normalize_sat_estado("Vigente"), "vigente")
        self.assertEqual(normalize_sat_estado("Cancelado"), "cancelado")
        self.assertEqual(normalize_sat_estado("En proceso"), "en_proceso")

    def test_parse_metadata_content(self):
        content = (
            b"Uuid|RfcEmisor|NombreEmisor|RfcReceptor|NombreReceptor|"
            b"FechaEmision|FechaCertificacion|Total|EfectoComprobante|Estado\n"
            b"AAA-BBB|EKU9003173C9|EMPRESA|AAA010101AAA|CLIENTE|"
            b"2026-01-01 10:00:00|2026-01-01 10:01:00|100.00|I|Cancelado\n"
        )
        rows = parse_metadata_content(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["uuid"], "AAA-BBB")
        self.assertEqual(rows[0]["estado_sat"], "cancelado")

    def test_build_request_fingerprint_stable(self):
        fi = datetime(2026, 1, 1)
        ff = datetime(2026, 1, 31)
        fp1 = build_request_fingerprint(1, "cfdi", "received", "metadata", fi, ff)
        fp2 = build_request_fingerprint(1, "cfdi", "received", "metadata", fi, ff)
        self.assertEqual(fp1, fp2)


@tagged("post_install", "-at_install")
class TestDownloadRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test",
            }
        )
        cls.env.user.groups_id |= cls.env.ref("l10n_mx_sat.group_sat_manager")

    def _create_request(self, **kwargs):
        vals = {
            "company_id": self.company.id,
            "document_kind": "cfdi",
            "direction": "received",
            "request_type": "xml",
            "fecha_inicial": "2026-02-01 00:00:00",
            "fecha_final": "2026-02-28 23:59:59",
            "state": "draft",
        }
        vals.update(kwargs)
        return self.env["l10n_mx_sat.download.request"].create(vals)

    def _mock_client(self, **overrides):
        client = MagicMock()
        client.authenticate.return_value = "fake-token"
        client.rfc = self.company.vat
        for attr, val in overrides.items():
            setattr(client, attr, val)
        return client

    def _patch_factory(self, mock_client):
        return patch.object(
            type(self.company),
            "l10n_mx_sat_get_client",
            return_value=mock_client,
        )

    def test_action_request_success(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "id_solicitud": "SOL-12345",
            "mensaje": "Solicitud aceptada",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "requested")
        self.assertEqual(req.id_solicitud, "SOL-12345")

    def test_action_request_duplicate_5002(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_DUPLICATE_LIFETIME,
            "id_solicitud": "",
            "mensaje": "Se agotaron las solicitudes",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "error")
        self.assertIn("5002", req.error_message)

    def test_action_request_max_elements_splits(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_MAX_ELEMENTS,
            "id_solicitud": "",
            "mensaje": "Tope maximo",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "draft")
        self.assertTrue(
            self.env["l10n_mx_sat.download.request"].search_count(
                [("company_id", "=", self.company.id)]
            )
            >= 2
        )

    def test_fingerprint_prevents_duplicate_request(self):
        req = self._create_request()
        with self.assertRaises(IntegrityError):
            self._create_request(
                fecha_inicial=req.fecha_inicial,
                fecha_final=req.fecha_final,
                document_kind=req.document_kind,
                direction=req.direction,
                request_type=req.request_type,
            )

    def test_metadata_upsert_updates_estado(self):
        request = self._create_request(request_type="metadata", state="done")
        row = {
            "uuid": "11111111-2222-3333-4444-555555555555",
            "rfc_emisor": "EKU9003173C9",
            "rfc_receptor": "AAA010101AAA",
            "estado_sat": "cancelado",
            "total": "150.00",
        }
        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            row, self.company, request
        )
        self.assertEqual(doc.estado_sat, "cancelado")
        row["estado_sat"] = "en_proceso"
        doc2 = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            row, self.company, request
        )
        self.assertEqual(doc2.id, doc.id)
        self.assertEqual(doc2.estado_sat, "en_proceso")

    def test_create_next_request_respects_metadata_window(self):
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        req = self.env["l10n_mx_sat.download.request"]._create_next_request(
            self.company, "cfdi", "received", "metadata"
        )
        self.assertTrue(req)
        delta = req.fecha_final - req.fecha_inicial
        self.assertLessEqual(delta.days, 7)

    def test_manual_sync_creates_requests(self):
        """Manual sync must create XML requests when none exist yet."""
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()

        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "id_solicitud": "SOL-MANUAL",
            "mensaje": "Solicitud aceptada",
        }
        with self._patch_factory(client):
            Request.with_context(
                l10n_mx_sat_manual_sync=True,
                test_queue_job_no_delay=True,
            )._cron_process_requests(companies=self.company)

        requests = Request.search([("company_id", "=", self.company.id)])
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(req.request_type == "xml" for req in requests))
        self.assertFalse(
            Request.search_count(
                [
                    ("company_id", "=", self.company.id),
                    ("request_type", "=", "metadata"),
                ]
            )
        )

    def test_manual_sync_respects_download_flags(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": True,
                "l10n_mx_sat_download_cfdi_received": False,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )

        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "id_solicitud": "SOL-FLAG",
            "mensaje": "Solicitud aceptada",
        }
        with self._patch_factory(client):
            Request.with_context(
                l10n_mx_sat_manual_sync=True,
                test_queue_job_no_delay=True,
            )._cron_process_requests(companies=self.company)

        requests = Request.search([("company_id", "=", self.company.id)])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.document_kind, "cfdi")
        self.assertEqual(requests.direction, "issued")
        self.assertEqual(requests.request_type, "xml")

    def test_manual_sync_with_all_flags_disabled_creates_nothing(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": False,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )

        Request.with_context(
            l10n_mx_sat_manual_sync=True,
            test_queue_job_no_delay=True,
        )._cron_process_requests(companies=self.company)

        self.assertEqual(
            Request.search_count([("company_id", "=", self.company.id)]),
            0,
        )

    def test_action_request_issued_uses_fiel_rfc_without_vat(self):
        self.company.vat = False
        client = self._mock_client()
        client.rfc = "RFCFIEL123"
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "id_solicitud": "SOL-ISSUED",
            "mensaje": "Solicitud aceptada",
        }
        req = self._create_request(document_kind="cfdi", direction="issued")
        with self._patch_factory(client):
            req._action_request()
        client.request_download.assert_called_once()
        self.assertEqual(client.request_download.call_args.args[1], "RFCFIEL123")
        self.assertEqual(req.state, "requested")

    def test_name_uses_fiel_rfc_when_vat_missing(self):
        self.company.vat = False
        client = self._mock_client()
        client.rfc = "RFCFIEL123"
        with self._patch_factory(client):
            req = self._create_request(document_kind="cfdi", direction="issued")
        self.assertTrue(req.name.startswith("RFCFIEL123 / CFDI / Emitido"))

    def test_action_verify_no_info_rejected_5004(self):
        """Real SAT pattern: verify OK but no packages in range."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "estado_solicitud": SAT_ESTADO_REJECTED,
            "codigo_estado_solicitud": SAT_CODE_NO_INFO,
            "numero_cfdis": 0,
            "paquetes": [],
            "mensaje": "Solicitud Aceptada",
        }
        req = self._create_request(
            document_kind="retention",
            direction="issued",
            state="requested",
            id_solicitud="012f356d-7d28-41a1-9c46-08c514aa5ed2",
        )
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 0)
        self.assertEqual(req.numero_cfdis, 0)
        self.assertFalse(req.error_message)

    def test_action_verify_rejected_without_no_info_is_error(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "estado_solicitud": SAT_ESTADO_REJECTED,
            "codigo_estado_solicitud": "5001",
            "numero_cfdis": 0,
            "paquetes": [],
            "mensaje": "Rechazada",
        }
        req = self._create_request(
            state="requested",
            id_solicitud="SOL-REJECT",
        )
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("EstadoSolicitud=5", req.error_message)
        self.assertIn("5001", req.error_message)

    def test_action_retry_from_error_without_id_solicitud(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "id_solicitud": "SOL-RETRY",
            "mensaje": "Solicitud aceptada",
        }
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "estado_solicitud": SAT_ESTADO_REJECTED,
            "codigo_estado_solicitud": SAT_CODE_NO_INFO,
            "numero_cfdis": 0,
            "paquetes": [],
            "mensaje": "Solicitud Aceptada",
        }
        req = self._create_request(state="error", error_message="Fallo inicial")
        count_before = self.env["l10n_mx_sat.download.request"].search_count(
            [("company_id", "=", self.company.id)]
        )
        with self._patch_factory(client):
            req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertFalse(req.error_message)
        self.assertEqual(
            self.env["l10n_mx_sat.download.request"].search_count(
                [("company_id", "=", self.company.id)]
            ),
            count_before,
        )

    def test_action_retry_from_error_with_id_solicitud(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "estado_solicitud": SAT_ESTADO_REJECTED,
            "codigo_estado_solicitud": SAT_CODE_NO_INFO,
            "numero_cfdis": 0,
            "paquetes": [],
            "mensaje": "Solicitud Aceptada",
        }
        req = self._create_request(
            state="error",
            id_solicitud="SOL-EXISTING",
            error_message="Error de verificacion previo",
        )
        with self._patch_factory(client):
            req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertFalse(req.error_message)
        client.request_download.assert_not_called()

    def test_can_retry_false_for_duplicate_5002(self):
        req = self._create_request(
            state="error",
            error_message="SAT: solicitud duplicada (5002).",
        )
        self.assertFalse(req.can_retry)


@tagged("post_install", "-at_install")
class TestMultiCompanySAT(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_mx_sat.group_sat_manager")
        cls.company_a = cls.env.ref("base.main_company")
        cls.company_a.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test-a",
            }
        )
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "Empresa B SAT",
                "vat": "AAA010101AAA",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test-b",
            }
        )

    def test_documents_isolated_by_company(self):
        req_a = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company_a.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "metadata",
                "fecha_inicial": "2026-01-01 00:00:00",
                "fecha_final": "2026-01-31 23:59:59",
                "state": "done",
            }
        )
        req_b = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company_b.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "metadata",
                "fecha_inicial": "2026-01-01 00:00:00",
                "fecha_final": "2026-01-31 23:59:59",
                "state": "done",
            }
        )
        uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {"uuid": uuid, "estado_sat": "vigente"},
            self.company_a,
            req_a,
        )
        self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {"uuid": uuid, "estado_sat": "cancelado"},
            self.company_b,
            req_b,
        )
        docs_a = (
            self.env["l10n_mx_sat.document"]
            .with_company(self.company_a)
            .search([("uuid", "=", uuid)])
        )
        docs_b = (
            self.env["l10n_mx_sat.document"]
            .with_company(self.company_b)
            .search([("uuid", "=", uuid)])
        )
        self.assertEqual(len(docs_a), 1)
        self.assertEqual(len(docs_b), 1)
        self.assertEqual(docs_a.estado_sat, "vigente")
        self.assertEqual(docs_b.estado_sat, "cancelado")
