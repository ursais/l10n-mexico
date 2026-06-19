# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import csv
import hashlib
import io
import re

# SAT metadata Estado values (case-insensitive normalization).
SAT_ESTADO_VIGENTE = "vigente"
SAT_ESTADO_CANCELADO = "cancelado"
SAT_ESTADO_EN_PROCESO = "en_proceso"

_ESTADO_MAP = {
    "vigente": SAT_ESTADO_VIGENTE,
    "cancelado": SAT_ESTADO_CANCELADO,
    "en proceso": SAT_ESTADO_EN_PROCESO,
    "enproceso": SAT_ESTADO_EN_PROCESO,
}


def normalize_sat_estado(value):
    """Normalize SAT metadata Estado column to internal selection keys."""
    if not value:
        return False
    key = str(value).strip().lower()
    key = re.sub(r"\s+", " ", key)
    return _ESTADO_MAP.get(key, key.replace(" ", "_"))


def build_request_fingerprint(
    company_id,
    document_kind,
    direction,
    request_type,
    fecha_inicial,
    fecha_final,
):
    """Build a stable fingerprint to avoid duplicate SAT requests (code 5002)."""
    payload = "|".join(
        [
            str(company_id),
            document_kind or "",
            direction or "",
            request_type or "",
            fecha_inicial.isoformat() if fecha_inicial else "",
            fecha_final.isoformat() if fecha_final else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_metadata_content(content_bytes):
    """Parse SAT metadata file content into list of dicts.

    SAT metadata files are typically pipe-delimited text with a header row.
    Column names vary slightly; we map common variants to normalized keys.
    """
    text = content_bytes.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return []

    delimiter = "|" if "|" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for raw in reader:
        normalized = {_normalize_header(k): (v or "").strip() for k, v in raw.items() if k}
        uuid = (
            normalized.get("uuid")
            or normalized.get("folio_fiscal")
            or normalized.get("foliofiscal")
        )
        if not uuid:
            continue
        rows.append(
            {
                "uuid": uuid.upper(),
                "rfc_emisor": normalized.get("rfc_emisor", ""),
                "nombre_emisor": normalized.get("nombre_emisor", ""),
                "rfc_receptor": normalized.get("rfc_receptor", ""),
                "nombre_receptor": normalized.get("nombre_receptor", ""),
                "fecha_emision": normalized.get("fecha_emision", ""),
                "fecha_certificacion": normalized.get("fecha_certificacion", ""),
                "fecha_timbrado": normalized.get("fecha_certificacion", ""),
                "pac_certifico": normalized.get("pac_certifico", ""),
                "total": normalized.get("total", ""),
                "efecto_comprobante": normalized.get("efecto_comprobante", ""),
                "tipo_comprobante": normalized.get("efecto_comprobante", ""),
                "estado_sat": normalize_sat_estado(
                    normalized.get("estado") or normalized.get("estatus")
                ),
                "fecha_cancelacion": normalized.get("fecha_cancelacion", ""),
            }
        )
    return rows


def _normalize_header(header):
    key = header.strip().lower()
    key = re.sub(r"[^\w\s]", "", key)
    key = re.sub(r"\s+", "_", key)
    aliases = {
        "foliofiscal": "uuid",
        "folio_fiscal": "uuid",
        "efecto": "efecto_comprobante",
        "estatus": "estado",
    }
    return aliases.get(key, key)
