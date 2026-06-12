# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml.etree import QName
from satcfdi.models import Signer
from satcfdi.pacs.sat import (
    SAT,
    EstadoComprobante,
    TipoDescargaMasivaTerceros,
)

class SatClient:
    """SAT web service adapter via satcfdi.

    Pure Python class with no Odoo ORM dependency.
    Swappable through the res.company.l10n_mx_sat_get_client() factory.
    """

    def __init__(self, cer_der, key_der, password):
        """Initialize the client with FIEL credentials.

        :param cer_der: certificate in DER format (bytes)
        :param key_der: private key in DER format (bytes)
        :param password: private key password (str)
        """
        signer = Signer.load(
            certificate=cer_der,
            key=key_der,
            password=password,
        )
        self._sat = SAT(signer=signer)

    def authenticate(self):
        """Authenticate with the SAT and return the token.

        satcfdi caches tokens internally for subsequent calls; this method
        performs authentication and returns the SAT token.

        :raises ValueError: if the token is empty
        :return: SAT authentication token
        :rtype: str
        """
        token_data = self._sat._autentica_comprobante()
        token = token_data.get("AutenticaResult")
        if not token:
            raise ValueError("SAT returned an empty token.")
        return token

    def request_download(self, token, rfc, fecha_inicial, fecha_final, **kwargs):
        """Send a download request to the SAT (Descarga Masiva).

        Defaults estado_comprobante to 'Vigente' because it is required by
        the SAT for CFDI download requests.

        :return: dict with keys cod_estatus, id_solicitud, mensaje
        """
        self._ensure_token(token)
        estado = kwargs.pop("estado_comprobante", None) or EstadoComprobante.VIGENTE
        tipo_solicitud = kwargs.pop("tipo_solicitud", TipoDescargaMasivaTerceros.CFDI)
        response = self._sat.recover_comprobante_received_request(
            fecha_inicial=fecha_inicial,
            fecha_final=fecha_final,
            rfc_receptor=kwargs.pop("rfc_receptor", rfc),
            rfc_emisor=kwargs.pop("rfc_emisor", None),
            tipo_solicitud=tipo_solicitud,
            tipo_comprobante=kwargs.pop("tipo_comprobante", None),
            estado_comprobante=estado,
            rfc_a_cuenta_terceros=kwargs.pop("rfc_a_cuenta_terceros", None),
            complemento=kwargs.pop("complemento", None),
        )
        return self._normalize_request_response(response)

    def verify_download(self, token, rfc, id_solicitud):
        """Check the status of a download request.

        :return: dict with keys estado_solicitud, paquetes, numero_cfdis, mensaje
        """
        self._ensure_token(token)
        response = self._sat.recover_comprobante_status(id_solicitud)
        return self._normalize_status_response(response)

    def download_package(self, token, rfc, id_paquete):
        """Download a package from the SAT.

        :return: dict with keys cod_estatus, paquete_b64, mensaje
        """
        self._ensure_token(token)
        response, paquete = self._sat.recover_comprobante_download(id_paquete)
        return self._normalize_download_response(response, paquete)

    def validate_cfdi(self, rfc_emisor, rfc_receptor, total, uuid):
        """Validate a CFDI status against the SAT.

        Uses the same public SAT consulta endpoint as satcfdi.pacs.sat.SAT.status.

        :return: dict with keys codigo_estatus, es_cancelable, estado
        """
        template = (
            '<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:tem="http://tempuri.org/"><Body><tem:Consulta>'
            "<tem:expresionImpresa>"
            f"<![CDATA[?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}]]>"
            "</tem:expresionImpresa></tem:Consulta></Body></Envelope>"
        )
        host = "https://consultaqr.facturaelectronica.sat.gob.mx"
        xml = self._sat._request(
            soap_url=f"{host}/ConsultaCFDIService.svc",
            data=template,
            soap_action="http://tempuri.org/IConsultaCFDIService/Consulta",
            verify=True,
            needs_token_fn=None,
        )
        result_node = xml.find("{*}Body/{*}ConsultaResponse/{*}ConsultaResult")
        result = {
            QName(item.tag).localname: item.text for item in result_node
        }
        return {
            "codigo_estatus": result.get("CodigoEstatus", ""),
            "es_cancelable": result.get("EsCancelable", ""),
            "estado": result.get("Estado", ""),
        }

    @staticmethod
    def _ensure_token(token):
        """Keep token parameter for API compatibility; satcfdi manages auth."""
        if not token:
            raise ValueError("SAT token is required.")

    @staticmethod
    def _normalize_request_response(response):
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "id_solicitud": response.get("IdSolicitud", ""),
            "mensaje": response.get("Mensaje", ""),
        }

    @staticmethod
    def _normalize_status_response(response):
        estado = response.get("EstadoSolicitud", 0)
        if hasattr(estado, "value"):
            estado = estado.value
        paquetes = response.get("IdsPaquetes") or []
        numero_cfdis = response.get("NumeroCFDIs", 0)
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "estado_solicitud": estado,
            "codigo_estado_solicitud": response.get("CodigoEstadoSolicitud", ""),
            "numero_cfdis": numero_cfdis,
            "paquetes": paquetes,
            "mensaje": response.get("Mensaje", ""),
        }

    @staticmethod
    def _normalize_download_response(response, paquete):
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "paquete_b64": paquete or "",
            "mensaje": response.get("Mensaje", ""),
        }
