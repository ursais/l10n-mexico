# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO

from lxml import etree

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_mx_sat.services import (
    MX_TZ,
    SAFE_XML_PARSER,
    SAT_CODE_DAILY_LIMIT,
    SAT_CODE_DUPLICATE_LIFETIME,
    SAT_CODE_MAX_ELEMENTS,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_DEFAULT_SYNC_DAYS,
    SAT_DOWNLOAD_EXPIRED,
    SAT_DOWNLOAD_MAX_REACHED,
    SAT_ESTADO_ACCEPTED,
    SAT_ESTADO_ERROR,
    SAT_ESTADO_EXPIRED,
    SAT_ESTADO_LABELS,
    SAT_ESTADO_PROCESSING,
    SAT_ESTADO_READY,
    SAT_ESTADO_REJECTED,
    SAT_STATUS_CODE_LABELS,
    SAT_METADATA_DEFAULT_WINDOW_DAYS,
    SAT_METADATA_MIN_WINDOW_HOURS,
    SAT_REJECT_CODES,
    sat_int,
    sat_str,
)
from odoo.addons.l10n_mx_sat.services.sat_metadata import (
    build_request_fingerprint,
    parse_metadata_content,
)

_logger = logging.getLogger(__name__)

# Active states: do not recreate identical fingerprint while one is open.
_ACTIVE_REQUEST_STATES = ("draft", "requested", "processing", "ready", "downloading")


class L10nMxSatDownloadRequest(models.Model):
    _name = "l10n_mx_sat.download.request"
    _description = "SAT Download Request"
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    document_kind = fields.Selection(
        selection=[
            ("cfdi", "CFDI"),
            ("retention", "Retencion"),
        ],
        required=True,
        default="cfdi",
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("issued", "Emitido"),
            ("received", "Recibido"),
        ],
        required=True,
        default="received",
        index=True,
    )
    request_type = fields.Selection(
        selection=[
            ("xml", "XML"),
            ("metadata", "Metadatos"),
        ],
        required=True,
        default="xml",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("requested", "Solicitado"),
            ("processing", "Procesando"),
            ("ready", "Listo"),
            ("downloading", "Descargando"),
            ("done", "Completado"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )
    fecha_inicial = fields.Datetime(string="Desde", required=True)
    fecha_final = fields.Datetime(string="Hasta", required=True)
    id_solicitud = fields.Char(string="ID solicitud SAT", readonly=True)
    request_fingerprint = fields.Char(
        string="Huella solicitud",
        readonly=True,
        index=True,
    )
    package_ids = fields.One2many(
        comodel_name="l10n_mx_sat.download.package",
        inverse_name="request_id",
        string="Paquetes",
        readonly=True,
    )
    document_ids = fields.One2many(
        comodel_name="l10n_mx_sat.document",
        inverse_name="download_request_id",
        string="Documentos",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    document_count = fields.Integer(string="Documentos procesados", readonly=True)
    numero_cfdis = fields.Integer(string="CFDIs reportados SAT", readonly=True)
    can_retry = fields.Boolean(
        string="Puede reintentar",
        compute="_compute_can_retry",
    )

    _sql_constraints = [
        (
            "request_fingerprint_uniq",
            "UNIQUE(request_fingerprint)",
            "Ya existe una solicitud SAT identica para esta empresa y rango.",
        )
    ]

    @api.depends(
        "company_id.vat",
        "company_id.l10n_mx_sat_fiel_cer",
        "company_id.l10n_mx_sat_fiel_key",
        "company_id.l10n_mx_sat_fiel_password",
        "document_kind",
        "direction",
        "request_type",
        "fecha_inicial",
        "fecha_final",
    )
    def _compute_name(self):
        for rec in self:
            rfc = rec._get_display_rfc(rec.company_id)
            kind = dict(rec._fields["document_kind"].selection).get(
                rec.document_kind, "?"
            )
            direction = dict(rec._fields["direction"].selection).get(rec.direction, "?")
            req_type = dict(rec._fields["request_type"].selection).get(
                rec.request_type, "?"
            )
            fi = rec.fecha_inicial.strftime("%Y-%m-%d") if rec.fecha_inicial else "?"
            ff = rec.fecha_final.strftime("%Y-%m-%d") if rec.fecha_final else "?"
            rec.name = f"{rfc} / {kind} / {direction} / {req_type} / {fi} - {ff}"

    @api.model
    def _get_display_rfc(self, company):
        """Resolve RFC for labels, falling back to FIEL when VAT is empty."""
        cache = getattr(self.env, "_l10n_mx_sat_display_rfc", None)
        if cache is None:
            cache = {}
            self.env._l10n_mx_sat_display_rfc = cache
        if company.id in cache:
            return cache[company.id]

        rfc = company.vat.strip().upper() if company.vat else False
        if not rfc and company.l10n_mx_sat_has_credentials():
            try:
                rfc = company.l10n_mx_sat_get_rfc()
            except Exception:
                rfc = False
        display = rfc or company.name or "?"
        cache[company.id] = display
        return display

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("request_fingerprint"):
                vals["request_fingerprint"] = self._build_fingerprint_from_vals(vals)
        return super().create(vals_list)

    @api.model
    def _build_fingerprint_from_vals(self, vals):
        company_id = vals.get("company_id") or self.env.company.id
        fecha_inicial = vals.get("fecha_inicial")
        fecha_final = vals.get("fecha_final")
        if isinstance(fecha_inicial, str):
            fecha_inicial = fields.Datetime.to_datetime(fecha_inicial)
        if isinstance(fecha_final, str):
            fecha_final = fields.Datetime.to_datetime(fecha_final)
        return build_request_fingerprint(
            company_id,
            vals.get("document_kind"),
            vals.get("direction"),
            vals.get("request_type"),
            fecha_inicial,
            fecha_final,
        )

    @api.depends("state", "error_message")
    def _compute_can_retry(self):
        non_retryable = (SAT_CODE_DUPLICATE_LIFETIME, SAT_CODE_DAILY_LIMIT)
        for rec in self:
            if rec.state != "error":
                rec.can_retry = False
                continue
            msg = rec.error_message or ""
            rec.can_retry = not any(code in msg for code in non_retryable)

    def _write_request_error(self, cod_estatus, mensaje):
        code_label = SAT_STATUS_CODE_LABELS.get(
            cod_estatus, cod_estatus or self.env._("(vacio)")
        )
        self.write(
            {
                "state": "error",
                "error_message": self.env._(
                    "SAT rechazo la solicitud de descarga. "
                    "CodEstatus=%(code)s (%(label)s). Mensaje SAT: %(message)s",
                    code=cod_estatus or self.env._("(vacio)"),
                    label=code_label,
                    message=mensaje or self.env._("(sin mensaje)"),
                ),
            }
        )

    def _complete_verify_no_info(self):
        """Mark verification as successful with zero documents in the range."""
        self.ensure_one()
        self.write(
            {
                "state": "done",
                "document_count": 0,
                "numero_cfdis": 0,
                "error_message": False,
            }
        )
        self._update_company_last_sync()

    def _format_verify_error(self, estado, codigo_estado, cod_estatus, mensaje):
        estado_label = SAT_ESTADO_LABELS.get(estado, str(estado))
        ces_label = SAT_STATUS_CODE_LABELS.get(
            codigo_estado, codigo_estado or self.env._("(vacio)")
        )
        ce_label = SAT_STATUS_CODE_LABELS.get(
            cod_estatus, cod_estatus or self.env._("(vacio)")
        )
        if estado == SAT_ESTADO_ERROR:
            return self.env._(
                "SAT reporto error en la solicitud (EstadoSolicitud=4, %(estado)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "La verificacion fue aceptada (CodEstatus=%(ce)s). "
                "Mensaje SAT: %(msg)s. Revise el rango de fechas o reintente.",
                estado=estado_label,
                ces=codigo_estado or self.env._("(vacio)"),
                ces_label=ces_label,
                ce=cod_estatus or self.env._("(vacio)"),
                msg=mensaje or self.env._("(sin mensaje)"),
            )
        if estado == SAT_ESTADO_REJECTED:
            return self.env._(
                "SAT rechazo la solicitud (EstadoSolicitud=5, %(estado)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "La verificacion fue aceptada (CodEstatus=%(ce)s, %(ce_label)s). "
                "Mensaje SAT: %(msg)s. Revise tipo, direccion y rango de fechas.",
                estado=estado_label,
                ces=codigo_estado or self.env._("(vacio)"),
                ces_label=ces_label,
                ce=cod_estatus or self.env._("(vacio)"),
                ce_label=ce_label,
                msg=mensaje or self.env._("(sin mensaje)"),
            )
        if estado == SAT_ESTADO_EXPIRED:
            return self.env._(
                "SAT marco la solicitud como vencida (EstadoSolicitud=6, %(estado)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "Use Reintentar para volver a solicitar el mismo rango.",
                estado=estado_label,
                ces=codigo_estado or self.env._("(vacio)"),
                ces_label=ces_label,
            )
        return self.env._(
            "SAT devolvio un estado de solicitud no reconocido "
            "(EstadoSolicitud=%(estado)s, %(estado_label)s). "
            "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
            "CodEstatus=%(ce)s (%(ce_label)s). Mensaje SAT: %(msg)s",
            estado=estado,
            estado_label=estado_label,
            ces=codigo_estado or self.env._("(vacio)"),
            ces_label=ces_label,
            ce=cod_estatus or self.env._("(vacio)"),
            ce_label=ce_label,
            msg=mensaje or self.env._("(sin mensaje)"),
        )

    def _action_request(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        result = client.request_download(
            token,
            rfc,
            self.fecha_inicial.replace(tzinfo=None),
            self.fecha_final.replace(tzinfo=None),
            document_kind=self.document_kind,
            direction=self.direction,
            request_type=self.request_type,
        )

        cod_estatus = sat_str(result.get("cod_estatus"))
        id_solicitud = sat_str(result.get("id_solicitud"))
        mensaje = sat_str(result.get("mensaje"))

        if cod_estatus == SAT_CODE_DUPLICATE_LIFETIME:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: solicitud duplicada (5002). No se reintentara "
                        "automaticamente con los mismos parametros."
                    ),
                }
            )
            return

        if id_solicitud and cod_estatus in (SAT_CODE_SUCCESS, SAT_CODE_NO_INFO):
            self.write(
                {
                    "state": "requested",
                    "id_solicitud": id_solicitud,
                    "error_message": False,
                }
            )
            return

        if cod_estatus == SAT_CODE_NO_INFO and not id_solicitud:
            self.write({"state": "done", "document_count": 0, "error_message": False})
            self._update_company_last_sync()
            return

        if cod_estatus == SAT_CODE_MAX_ELEMENTS:
            self._handle_max_elements_exceeded()
            return

        if cod_estatus in SAT_REJECT_CODES:
            self._write_request_error(cod_estatus, mensaje)
            return

        if id_solicitud and "aceptada" in mensaje.lower():
            self.write(
                {
                    "state": "requested",
                    "id_solicitud": id_solicitud,
                    "error_message": False,
                }
            )
            return

        self._write_request_error(cod_estatus, mensaje)

    def _handle_max_elements_exceeded(self):
        """Split request window on SAT 5003 (metadata/XML volume limit)."""
        self.ensure_one()
        delta = self.fecha_final - self.fecha_inicial
        min_delta = timedelta(hours=SAT_METADATA_MIN_WINDOW_HOURS)
        if delta <= min_delta:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: maximo de registros excedido incluso con "
                        "ventana minima. Revise manualmente."
                    ),
                }
            )
            return

        mid = self.fecha_inicial + (delta / 2)
        # Current request covers first half; create second half if not duplicate.
        self.write(
            {
                "fecha_final": mid,
                "state": "draft",
                "request_fingerprint": build_request_fingerprint(
                    self.company_id.id,
                    self.document_kind,
                    self.direction,
                    self.request_type,
                    self.fecha_inicial,
                    mid,
                ),
                "error_message": self.env._(
                    "Ventana reducida automaticamente por SAT 5003."
                ),
            }
        )
        second_half = self.search(
            [
                (
                    "request_fingerprint",
                    "=",
                    build_request_fingerprint(
                        self.company_id.id,
                        self.document_kind,
                        self.direction,
                        self.request_type,
                        mid + timedelta(seconds=1),
                        self.fecha_final,
                    ),
                )
            ],
            limit=1,
        )
        if not second_half:
            self.create(
                {
                    "company_id": self.company_id.id,
                    "document_kind": self.document_kind,
                    "direction": self.direction,
                    "request_type": self.request_type,
                    "fecha_inicial": mid + timedelta(seconds=1),
                    "fecha_final": self.fecha_final,
                    "state": "draft",
                }
            )

    def _action_verify(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        result = client.verify_download(
            token, rfc, self.id_solicitud, document_kind=self.document_kind
        )

        cod_estatus = sat_str(result.get("cod_estatus"))
        estado = sat_int(result.get("estado_solicitud"), 0)
        codigo_estado = sat_str(result.get("codigo_estado_solicitud"))
        paquetes = result.get("paquetes") or []
        numero_cfdis = sat_int(result.get("numero_cfdis"), 0)
        mensaje = sat_str(result.get("mensaje"))

        if cod_estatus == SAT_CODE_MAX_ELEMENTS:
            self._handle_max_elements_exceeded()
            return

        if cod_estatus == SAT_CODE_DAILY_LIMIT:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: limite diario de descarga alcanzado. Reintente mañana."
                    ),
                }
            )
            return

        if cod_estatus == SAT_CODE_DUPLICATE_LIFETIME:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: limite de solicitudes duplicadas alcanzado (5002)."
                    ),
                }
            )
            return

        if codigo_estado == SAT_CODE_NO_INFO or cod_estatus == SAT_CODE_NO_INFO:
            self._complete_verify_no_info()
            return

        if estado in (SAT_ESTADO_ACCEPTED, SAT_ESTADO_PROCESSING):
            self.write({"state": "processing", "numero_cfdis": numero_cfdis})
        elif estado == SAT_ESTADO_READY:
            existing_ids = set(self.package_ids.mapped("id_paquete"))
            for id_paquete in paquetes:
                if id_paquete in existing_ids:
                    continue
                self.env["l10n_mx_sat.download.package"].create(
                    {
                        "request_id": self.id,
                        "id_paquete": id_paquete,
                        "state": "pending",
                    }
                )
            self.write(
                {
                    "state": "ready",
                    "numero_cfdis": numero_cfdis,
                    "error_message": False,
                }
            )
        elif estado == 0:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT devolvio un EstadoSolicitud invalido (0). "
                        "CodEstatus=%(ce)s (%(ce_label)s). "
                        "CodigoEstadoSolicitud=%(ces)s. Mensaje SAT: %(msg)s",
                        ce=cod_estatus or self.env._("(vacio)"),
                        ce_label=SAT_STATUS_CODE_LABELS.get(
                            cod_estatus, cod_estatus or self.env._("(vacio)")
                        ),
                        ces=codigo_estado or self.env._("(vacio)"),
                        msg=mensaje or self.env._("(sin mensaje)"),
                    ),
                }
            )
        else:
            self.write(
                {
                    "state": "error",
                    "error_message": self._format_verify_error(
                        estado, codigo_estado, cod_estatus, mensaje
                    ),
                }
            )

    def _get_retry_target_state(self):
        """Return the pipeline state to resume after a failed request."""
        self.ensure_one()
        if not self.id_solicitud:
            return "draft"
        retry_packages = self.package_ids.filtered(
            lambda p: p.state in ("pending", "error")
        )
        if retry_packages:
            retry_packages.filtered(lambda p: p.state == "error").write(
                {"state": "pending"}
            )
            return "ready"
        return "requested"

    def _process_request_pipeline(self):
        """Run the SAT download pipeline for the current request state."""
        self.ensure_one()
        if self.state == "draft":
            self._action_request()
        if self.state in ("requested", "processing"):
            self._action_verify()
        if self.state == "ready":
            self._action_download()

    def action_retry(self):
        """Retry a failed SAT download request from the appropriate step."""
        self.ensure_one()
        if self.state != "error":
            raise UserError(
                self.env._("Solo se pueden reintentar solicitudes en estado de error.")
            )
        if not self.can_retry:
            raise UserError(
                self.env._(
                    "Esta solicitud no puede reintentarse automaticamente. "
                    "Revise el mensaje de error."
                )
            )

        target_state = self._get_retry_target_state()
        self.write({"state": target_state, "error_message": False})

        try:
            with self.env.cr.savepoint():
                self._process_request_pipeline()
        except Exception as e:
            self.write({"state": "error", "error_message": str(e)})
            raise UserError(
                self.env._("Error al reintentar solicitud SAT: %s", e)
            ) from e

        if self.state == "done":
            message = self.env._(
                "Solicitud completada. Documentos procesados: %(count)s.",
                count=self.document_count,
            )
            notif_type = "success"
        elif self.state == "error":
            message = self.error_message or self.env._(
                "La solicitud volvio a fallar."
            )
            notif_type = "danger"
        else:
            message = self.env._(
                "Reintento iniciado. Estado actual: %(state)s.",
                state=dict(self._fields["state"].selection).get(self.state, self.state),
            )
            notif_type = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Reintento SAT"),
                "message": message,
                "type": notif_type,
                "sticky": self.state == "error",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _action_download(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        self.write({"state": "downloading"})

        documents = self.env["l10n_mx_sat.document"]
        document_count = 0

        for package in self.package_ids.filtered(lambda p: p.state == "pending"):
            try:
                result = client.download_package(
                    token,
                    rfc,
                    package.id_paquete,
                    document_kind=self.document_kind,
                )
                cod_estatus = sat_str(result.get("cod_estatus"))
                paquete_b64 = result.get("paquete_b64", "")

                if cod_estatus in (SAT_DOWNLOAD_EXPIRED, SAT_DOWNLOAD_MAX_REACHED):
                    package.write({"state": "error"})
                    continue
                if cod_estatus != SAT_CODE_SUCCESS or not paquete_b64:
                    package.write({"state": "error"})
                    continue

                proc = self._process_package(paquete_b64, company)
                documents |= proc["documents"]
                document_count += proc["processed"]
                package.write({"state": "processed"})
            except Exception:
                package.write({"state": "error"})
                _logger.exception("Error processing package %s", package.id_paquete)

        all_error = self.package_ids and all(
            p.state == "error" for p in self.package_ids
        )
        if all_error:
            self.write(
                {
                    "state": "error",
                    "document_count": document_count,
                    "error_message": self.env._("Todos los paquetes fallaron."),
                }
            )
        else:
            self.write(
                {
                    "state": "done",
                    "document_count": document_count,
                    "error_message": False,
                }
            )
            self._update_company_last_sync()

    def _update_company_last_sync(self):
        self.ensure_one()
        field_name = (
            "l10n_mx_sat_last_metadata_sync"
            if self.request_type == "metadata"
            else "l10n_mx_sat_last_sync"
        )
        self.company_id.sudo().write({field_name: fields.Datetime.now()})

    _ZIP_MAX_SIZE = 500 * 1024 * 1024
    _ZIP_MAX_FILES = 10_000

    def _process_package(self, paquete_b64, company):
        """Extract ZIP and process XML or metadata files."""
        documents = self.env["l10n_mx_sat.document"]
        processed = 0

        zip_data = base64.b64decode(paquete_b64)
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            total_size = sum(info.file_size for info in zf.infolist())
            file_count = len(zf.namelist())
            if total_size > self._ZIP_MAX_SIZE or file_count > self._ZIP_MAX_FILES:
                _logger.warning("ZIP bomb guard triggered")
                return {"documents": documents, "processed": 0}

            for filename in zf.namelist():
                lower = filename.lower()
                content = zf.read(filename)
                if self.request_type == "metadata":
                    if not lower.endswith((".txt", ".csv")):
                        continue
                    rows = parse_metadata_content(content)
                    for row in rows:
                        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
                            row, company, self
                        )
                        if doc:
                            documents |= doc
                            processed += 1
                elif lower.endswith(".xml"):
                    try:
                        tree = etree.fromstring(content, SAFE_XML_PARSER)
                    except etree.XMLSyntaxError:
                        continue
                    doc = self.env["l10n_mx_sat.document"]._upsert_from_xml(
                        tree, content, company, self
                    )
                    if doc:
                        documents |= doc
                        processed += 1

        return {"documents": documents, "processed": processed}

    @api.model
    def _cron_process_requests(self, companies=None):
        """Main cron entry point."""
        if companies is None:
            companies = self.env["res.company"].search(
                [
                    ("l10n_mx_sat_auto_download", "=", True),
                    ("l10n_mx_sat_fiel_cer", "!=", False),
                    ("l10n_mx_sat_fiel_key", "!=", False),
                    ("l10n_mx_sat_fiel_password", "!=", False),
                ]
            )

        manual_sync = self.env.context.get("l10n_mx_sat_manual_sync")

        for company in companies:
            # Always ensure requests exist. Manual sync previously skipped this
            # and only processed pending rows, so "Sync now" did nothing on
            # a fresh company with no requests yet.
            self._ensure_scheduled_requests(company)
            if not self.env.context.get("test_queue_job_no_delay"):
                self.env.cr.commit()  # pylint: disable=invalid-commit

            pending_requests = self.search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", _ACTIVE_REQUEST_STATES),
                ],
                order="create_date asc",
            )

            successful_requests = self.browse()
            for req in pending_requests:
                try:
                    with self.env.cr.savepoint():
                        if req.state == "draft":
                            req._action_request()
                        if req.state in ("requested", "processing"):
                            req._action_verify()
                        if req.state == "ready":
                            req._action_download()
                        if req.state == "done":
                            successful_requests |= req
                    if not self.env.context.get("test_queue_job_no_delay"):
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                except Exception as e:
                    req_safe = req.exists()
                    if req_safe:
                        req_safe.write({"state": "error", "error_message": str(e)})
                    if not self.env.context.get("test_queue_job_no_delay"):
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                    _logger.exception("Error processing SAT request id=%s", req.id)

            if not manual_sync and successful_requests:
                self._ensure_scheduled_requests(company, after_success=True)

    @api.model
    def _ensure_scheduled_requests(self, company, after_success=False):
        """Create missing XML download requests for enabled company flows."""
        flows = company.l10n_mx_sat_get_xml_download_flows()
        if not flows:
            return
        for document_kind, direction, request_type in flows:
            pending = self.search_count(
                [
                    ("company_id", "=", company.id),
                    ("document_kind", "=", document_kind),
                    ("direction", "=", direction),
                    ("request_type", "=", request_type),
                    ("state", "in", _ACTIVE_REQUEST_STATES),
                ]
            )
            if pending:
                continue
            last_error = self.search(
                [
                    ("company_id", "=", company.id),
                    ("document_kind", "=", document_kind),
                    ("direction", "=", direction),
                    ("request_type", "=", request_type),
                    ("state", "=", "error"),
                ],
                order="write_date desc",
                limit=1,
            )
            if last_error and SAT_CODE_DUPLICATE_LIFETIME in (last_error.error_message or ""):
                continue
            req = self._create_next_request(
                company, document_kind, direction, request_type
            )
            if req and after_success:
                _logger.info(
                    "Chained SAT request %s for company %s",
                    req.name,
                    company.name,
                )

    @api.model
    def _create_next_request(self, company, document_kind, direction, request_type):
        """Create incremental request for the next date window."""
        last_done = self.search(
            [
                ("company_id", "=", company.id),
                ("document_kind", "=", document_kind),
                ("direction", "=", direction),
                ("request_type", "=", request_type),
                ("state", "=", "done"),
            ],
            order="fecha_final desc",
            limit=1,
        )

        sync_from = self._get_sync_from_date(company, request_type)
        if last_done:
            fecha_inicial = last_done.fecha_final + timedelta(seconds=1)
        elif sync_from:
            fecha_inicial = datetime.combine(sync_from, datetime.min.time())
        else:
            mx_now = datetime.now(MX_TZ)
            days = (
                SAT_METADATA_DEFAULT_WINDOW_DAYS
                if request_type == "metadata"
                else SAT_DEFAULT_SYNC_DAYS
            )
            fecha_inicial = (mx_now - timedelta(days=days)).replace(
                hour=0, minute=0, second=0, tzinfo=None
            )

        mx_now = datetime.now(MX_TZ)
        fecha_final = (mx_now - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, tzinfo=None
        )

        if hasattr(fecha_inicial, "tzinfo") and fecha_inicial.tzinfo:
            fecha_inicial = fecha_inicial.replace(tzinfo=None)

        if request_type == "metadata" and not last_done:
            window_end = fecha_inicial + timedelta(days=SAT_METADATA_DEFAULT_WINDOW_DAYS)
            if window_end < fecha_final:
                fecha_final = window_end.replace(hour=23, minute=59, second=59)

        if fecha_inicial >= fecha_final:
            return self.browse()

        fingerprint = build_request_fingerprint(
            company.id,
            document_kind,
            direction,
            request_type,
            fecha_inicial,
            fecha_final,
        )
        if self.search([("request_fingerprint", "=", fingerprint)], limit=1):
            return self.browse()

        return self.create(
            {
                "company_id": company.id,
                "document_kind": document_kind,
                "direction": direction,
                "request_type": request_type,
                "fecha_inicial": fecha_inicial,
                "fecha_final": fecha_final,
                "state": "draft",
                "request_fingerprint": fingerprint,
            }
        )

    @api.model
    def _get_sync_from_date(self, company, request_type):
        if request_type == "metadata":
            return (
                company.l10n_mx_sat_metadata_sync_from or company.l10n_mx_sat_sync_from
            )
        return company.l10n_mx_sat_sync_from


class L10nMxSatDownloadPackage(models.Model):
    _name = "l10n_mx_sat.download.package"
    _description = "SAT Download Package"

    request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        index=True,
    )
    id_paquete = fields.Char(string="ID paquete", required=True, readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("processed", "Procesado"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        readonly=True,
    )
