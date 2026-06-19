# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from datetime import datetime as dt

from lxml import etree

from odoo import api, fields, models

from ..services import SAFE_XML_PARSER
from ..services.sat_metadata import (
    SAT_ESTADO_CANCELADO,
    SAT_ESTADO_EN_PROCESO,
    SAT_ESTADO_VIGENTE,
    normalize_sat_estado,
)

_logger = logging.getLogger(__name__)

CFDI_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class L10nMxSatDocument(models.Model):
    _name = "l10n_mx_sat.document"
    _description = "SAT Document"
    _order = "fecha_emision desc, uuid"
    _rec_name = "display_name"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    uuid = fields.Char(required=True, index=True)
    document_kind = fields.Selection(
        selection=[
            ("cfdi", "CFDI"),
            ("retention", "Retencion"),
        ],
        required=True,
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("issued", "Emitido"),
            ("received", "Recibido"),
        ],
        required=True,
        index=True,
    )
    estado_sat = fields.Selection(
        selection=[
            (SAT_ESTADO_VIGENTE, "Vigente"),
            (SAT_ESTADO_CANCELADO, "Cancelado"),
            (SAT_ESTADO_EN_PROCESO, "En proceso"),
        ],
        string="Estado SAT",
        index=True,
    )
    tipo_comprobante = fields.Char(string="Tipo comprobante", index=True)
    rfc_emisor = fields.Char(index=True)
    nombre_emisor = fields.Char()
    rfc_receptor = fields.Char(index=True)
    nombre_receptor = fields.Char()
    fecha_emision = fields.Datetime(index=True)
    fecha_timbrado = fields.Datetime()
    fecha_cancelacion = fields.Datetime()
    total = fields.Float(digits=(16, 6))
    moneda = fields.Char()
    serie = fields.Char()
    folio = fields.Char()
    has_xml = fields.Boolean(default=False, index=True)
    download_request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        string="Solicitud SAT",
        readonly=True,
        ondelete="set null",
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="XML",
        readonly=True,
        ondelete="set null",
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        (
            "uuid_company_kind_direction_uniq",
            "UNIQUE(uuid, company_id, document_kind, direction)",
            "Ya existe un documento SAT con este UUID para esta empresa.",
        )
    ]

    @api.depends("uuid", "document_kind", "direction", "company_id.vat")
    def _compute_display_name(self):
        for doc in self:
            parts = [doc.uuid or "?"]
            if doc.document_kind:
                parts.append(dict(doc._fields["document_kind"].selection).get(doc.document_kind))
            if doc.direction:
                parts.append(dict(doc._fields["direction"].selection).get(doc.direction))
            doc.display_name = " / ".join(parts)

    @api.model
    def _find_document(self, uuid, company, document_kind, direction):
        return self.search(
            [
                ("uuid", "=", uuid),
                ("company_id", "=", company.id),
                ("document_kind", "=", document_kind),
                ("direction", "=", direction),
            ],
            limit=1,
        )

    @api.model
    def _upsert_from_metadata_row(self, row, company, request):
        """Create or update a document from SAT metadata row."""
        uuid = (row.get("uuid") or "").upper()
        if not uuid:
            return self.browse()

        document = self._find_document(
            uuid, company, request.document_kind, request.direction
        )
        write_vals = {"download_request_id": request.id}
        field_map = (
            ("estado_sat", "estado_sat"),
            ("rfc_emisor", "rfc_emisor"),
            ("nombre_emisor", "nombre_emisor"),
            ("rfc_receptor", "rfc_receptor"),
            ("nombre_receptor", "nombre_receptor"),
            ("tipo_comprobante", "tipo_comprobante"),
        )
        for target, source in field_map:
            value = row.get(source)
            if value:
                write_vals[target] = value
            elif document:
                write_vals[target] = document[target]

        if row.get("total"):
            try:
                write_vals["total"] = float(row["total"])
            except (TypeError, ValueError):
                pass
        for date_field, row_key in (
            ("fecha_emision", "fecha_emision"),
            ("fecha_timbrado", "fecha_timbrado"),
            ("fecha_cancelacion", "fecha_cancelacion"),
        ):
            parsed = self._parse_sat_datetime(row.get(row_key))
            if parsed:
                write_vals[date_field] = parsed

        if document:
            document.write({k: v for k, v in write_vals.items() if v is not None})
            return document

        return self.create(
            {
                "company_id": company.id,
                "uuid": uuid,
                "document_kind": request.document_kind,
                "direction": request.direction,
                **write_vals,
            }
        )

    @api.model
    def _upsert_from_xml(self, tree, xml_bytes, company, request):
        """Create or update a document from a CFDI/retencion XML."""
        uuid = self._extract_uuid(tree)
        if not uuid:
            _logger.warning("XML without UUID, skipping")
            return self.browse()

        if not self._validate_xml_company(tree, company, request):
            return self.browse()

        vals = self._parse_xml_values(tree, request.document_kind)
        document = self._find_document(
            uuid, company, request.document_kind, request.direction
        )
        vals["download_request_id"] = request.id
        vals["has_xml"] = True

        if document:
            document.write({k: v for k, v in vals.items() if v is not None})
        else:
            document = self.create(
                {
                    "company_id": company.id,
                    "uuid": uuid,
                    "document_kind": request.document_kind,
                    "direction": request.direction,
                    **vals,
                }
            )

        attachment = document.attachment_id
        attachment_vals = {
            "name": f"{uuid}.xml",
            "raw": xml_bytes,
            "res_model": self._name,
            "res_id": document.id,
            "mimetype": "application/xml",
            "company_id": company.id,
        }
        if attachment:
            attachment.write({"raw": xml_bytes})
        else:
            attachment = self.env["ir.attachment"].create(attachment_vals)
            document.attachment_id = attachment.id
        return document

    @api.model
    def _extract_uuid(self, tree):
        tfd_nodes = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
        if tfd_nodes:
            uuid = tfd_nodes[0].get("UUID")
            if uuid:
                return uuid.upper()
        folio = tree.get("FolioFiscal") or tree.get("UUID")
        return folio.upper() if folio else False

    @api.model
    def _validate_xml_company(self, tree, company, request):
        company_vat = (company.vat or "").strip().upper()
        if request.document_kind == "cfdi":
            if request.direction == "received":
                receptor = tree.find("{*}Receptor")
                if receptor is None:
                    return False
                rfc = (receptor.get("Rfc") or "").upper()
                return rfc == company_vat
            emisor = tree.find("{*}Emisor")
            if emisor is None:
                return False
            rfc = (emisor.get("Rfc") or "").upper()
            return rfc == company_vat
        # Retenciones: validate Emisor/Receptor similarly
        if request.direction == "received":
            receptor = tree.find(".//*[local-name()='Receptor']")
            if receptor is not None:
                rfc = (receptor.get("Rfc") or receptor.get("RfcReceptor") or "").upper()
                return not company_vat or rfc == company_vat
        emisor = tree.find(".//*[local-name()='Emisor']")
        if emisor is not None:
            rfc = (emisor.get("Rfc") or emisor.get("RfcEmisor") or "").upper()
            return not company_vat or rfc == company_vat
        return True

    @api.model
    def _parse_xml_values(self, tree, document_kind):
        vals = {}
        if document_kind == "cfdi":
            emisor = tree.find("{*}Emisor")
            receptor = tree.find("{*}Receptor")
            if emisor is not None:
                vals["rfc_emisor"] = emisor.get("Rfc")
                vals["nombre_emisor"] = emisor.get("Nombre")
            if receptor is not None:
                vals["rfc_receptor"] = receptor.get("Rfc")
                vals["nombre_receptor"] = receptor.get("Nombre")
            vals["tipo_comprobante"] = tree.get("TipoDeComprobante")
            vals["moneda"] = tree.get("Moneda")
            vals["serie"] = tree.get("Serie")
            vals["folio"] = tree.get("Folio")
            try:
                vals["total"] = float(tree.get("Total") or 0)
            except (TypeError, ValueError):
                pass
            vals["fecha_emision"] = self._parse_sat_datetime(tree.get("Fecha"))
            tfd = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
            if tfd:
                vals["fecha_timbrado"] = self._parse_sat_datetime(tfd[0].get("FechaTimbrado"))
        else:
            emisor = tree.find(".//*[local-name()='Emisor']")
            receptor = tree.find(".//*[local-name()='Receptor']")
            if emisor is not None:
                vals["rfc_emisor"] = emisor.get("Rfc") or emisor.get("RfcEmisor")
                vals["nombre_emisor"] = emisor.get("Nombre") or emisor.get("NomDenRazSocE")
            if receptor is not None:
                vals["rfc_receptor"] = receptor.get("Rfc") or receptor.get("RfcReceptor")
                vals["nombre_receptor"] = receptor.get("Nombre") or receptor.get("NomDenRazSocR")
            vals["fecha_emision"] = self._parse_sat_datetime(
                tree.get("FechaExp") or tree.get("Fecha")
            )
            try:
                vals["total"] = float(tree.get("MontoTotOperacion") or tree.get("Total") or 0)
            except (TypeError, ValueError):
                pass
        if not vals.get("estado_sat"):
            vals["estado_sat"] = SAT_ESTADO_VIGENTE
        return vals

    @api.model
    def _parse_sat_datetime(self, value):
        if not value:
            return False
        value = str(value).strip()
        for fmt, size in (
            (CFDI_DATE_FORMAT, 19),
            ("%Y-%m-%d %H:%M:%S", 19),
            ("%Y-%m-%d", 10),
        ):
            try:
                return dt.strptime(value[:size], fmt)
            except ValueError:
                continue
        return False

    def action_download_xml(self):
        self.ensure_one()
        if not self.attachment_id:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=true",
            "target": "self",
        }

    @api.model
    def _update_estado_from_validate(self, document, validate_result):
        estado = normalize_sat_estado(validate_result.get("estado"))
        if estado:
            document.estado_sat = estado
