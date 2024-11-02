import base64
import json
import logging
import random
import string
from datetime import datetime
from json.decoder import JSONDecodeError

import requests
from lxml import etree
from zeep import Client
from zeep.transports import Transport

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class AccountEdiFormat(models.Model):
    _inherit = "account.edi.format"

    # -------------------------------------------------------------------------
    # CFDI: Helpers
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_mx_hr_payroll_edi_get_serie_and_folio(self, payslip):
        serie_number = "SLIP"
        folio_number = payslip.number
        return {
            "serie_number": serie_number,
            "folio_number": folio_number.replace("/", ""),
        }

    @api.model
    def _l10n_mx_hr_payroll_edi_check_configuration(self, payslip):
        company = payslip.company_id
        pac_name = company.l10n_mx_hr_payroll_edi_pac

        errors = []

        # == Check the certificate ==
        certificate = company.l10n_mx_hr_payroll_edi_certificate_ids.sudo().get_valid_certificate()
        if not certificate:
            errors.append(_("No valid certificate found"))

        # == Check the credentials to call the PAC web-service ==
        if pac_name:
            pac_test_env = company.l10n_mx_hr_payroll_edi_pac_test_env
            pac_password = company.l10n_mx_hr_payroll_edi_pac_password
            if not pac_test_env and not pac_password:
                errors.append(_("No PAC credentials specified."))
        else:
            errors.append(_("No PAC specified."))

        # == Check the 'l10n_mx_edi_decimal_places' field set on the currency  ==
        currency_precision = payslip.currency_id.l10n_mx_edi_decimal_places
        if currency_precision is False:
            errors.append(
                _(
                    "The SAT does not provide information for the currency %s.\n"
                    "You must get manually a key from the PAC to confirm the "
                    "currency rate is accurate enough."
                )
                % payslip.currency_id
            )

        return errors

    # -------------------------------------------------------------------------
    # BUSINESS FLOW: EDI
    # -------------------------------------------------------------------------

    def _check_move_configuration(self, payslip):
        if self.code != "cfdi_1_2":
            return super()._check_move_configuration(payslip)
        return self._l10n_mx_hr_payroll_edi_check_configuration(payslip)

    def _get_payslip_edi_content(self, payslip):
        if self.code != "cfdi_1_2":
            return super()._get_payslip_edi_content(payslip)
        return self._l10n_mx_hr_payroll_edi_export_payslip_cfdi(payslip).get("cfdi_str")

    def _needs_web_services(self):
        # OVERRIDE
        return self.code == "cfdi_1_2" or super()._needs_web_services()

    def _is_compatible_with_journal(self, journal):
        # OVERRIDE
        self.ensure_one()
        if self.code != "cfdi_1_2":
            return super()._is_compatible_with_journal(journal)
        return (
            journal.type == "general"
            and journal.country_code == "MX"
            and journal.company_id.currency_id.name == "MXN"
        )

    @api.model
    def _l10n_mx_hr_payroll_edi_format_error_message(self, error_title, errors):
        bullet_list_msg = "".join("<li>%s</li>" % msg for msg in errors)
        return "%s<ul>%s</ul>" % (error_title, bullet_list_msg)

    # -------------------------------------------------------------------------
    # CFDI Generation: Generic
    # ----------------------------------------

    def _l10n_mx_hr_payroll_edi_get_common_cfdi_values(self, payslip):
        """Generic values to generate a cfdi for a journal entry.
        :param move:    The account.move record to which generate the CFDI.
        :return:        A python dictionary.
        """

        def _format_string_cfdi(text, size=100):
            """Replace from text received the characters that are not found in the
            regex. This regex is taken from SAT documentation
            https://goo.gl/C9sKH6
            text: Text to remove extra characters
            size: Cut the string in size len
            Ex. 'Product ABC (small size)' - 'Product ABC small size'"""
            if not text:
                return None
            text = text.replace("|", " ")
            return text.strip()[:size]

        def _format_float_cfdi(amount, precision):
            if amount is None or amount is False:
                return None
            return "%.*f" % (
                precision,
                amount
                if not float_is_zero(amount, precision_digits=precision)
                else 0.0,
            )

        company = payslip.company_id
        certificate = company.l10n_mx_hr_payroll_edi_certificate_ids.sudo().get_valid_certificate()
        currency_precision = payslip.currency_id.l10n_mx_edi_decimal_places

        customer = payslip.contract_id.employee_id.address_home_id
        employee = payslip.employee_id
        contract = payslip.contract_id
        supplier = payslip.company_id.partner_id.commercial_partner_id

        if not customer:
            customer_rfc = False
        elif customer.country_id and customer.country_id.code != "MX":
            customer_rfc = "XEXX010101000"
        elif customer.vat:
            customer_rfc = customer.vat.strip()
        elif customer.country_id.code in (False, "MX"):
            customer_rfc = "XAXX010101000"
        else:
            customer_rfc = "XEXX010101000"
        if payslip.l10n_mx_edi_origin:
            origin_type, origin_uuids = payslip._l10n_mx_edi_read_cfdi_origin(
                payslip.l10n_mx_edi_origin
            )
        else:
            origin_type = None
            origin_uuids = []

        return {
            **self._l10n_mx_hr_payroll_edi_get_serie_and_folio(payslip),
            "certificate": certificate,
            "certificate_number": certificate.serial_number,
            "certificate_key": certificate.sudo()._get_data()[0].decode("utf-8"),
            "record": payslip,
            "supplier": supplier,
            "customer": customer,
            "employee": employee,
            "contract": contract,
            "customer_rfc": customer_rfc,
            "issued_address": payslip._get_l10n_mx_hr_payroll_edi_issued_address(),
            "currency_precision": currency_precision,
            "origin_type": origin_type,
            "origin_uuids": origin_uuids,
            "format_string": _format_string_cfdi,
            "format_float": _format_float_cfdi,
        }

    # -------------------------------------------------------------------------
    # CFDI Generation: Payslip
    # -------------------------------------------------------------------------

    def _l10n_mx_hr_payroll_edi_get_payslip_line_cfdi_values(self, payslip, line):
        cfdi_values = {"line": line}

        return cfdi_values

    def _l10n_mx_hr_payroll_edi_get_payslip_cfdi_values(self, payslip):
        cfdi_date = datetime.combine(
            fields.Datetime.from_string(payslip.payslip_date),
            payslip.l10n_mx_edi_post_time.time(),
        ).strftime("%Y-%m-%dT%H:%M:%S")

        cfdi_values = {
            **self._l10n_mx_hr_payroll_edi_get_common_cfdi_values(payslip),
            "currency_name": payslip.currency_id.name,
            "employee": payslip.employee_id,
            "numdiaspagados": (payslip.date_to - payslip.date_from).days + 1,
            "antiguedad": payslip._l10n_mx_payroll_antiguedad(),
            "tiponomina": "O"
            if payslip.contract_id.period_cfdi.type_id.payroll_type == "O"
            else "E",
            "banco": payslip.employee_id.bank_account_id.bank_id.l10n_mx_edi_code
            or False,
            "payment_method_code": (
                payslip.l10n_mx_edi_payment_method_id.code or ""
            ).replace("NA", "99"),
            "cfdi_date": cfdi_date,
        }

        # ==== Payslip Values ====

        payslip_lines = payslip.line_ids.filtered(
            lambda payslip: payslip.appears_on_payslip
        )

        if payslip.currency_id.name == "MXN":
            cfdi_values["currency_conversion_rate"] = None
        else:
            # assumes that invoice.company_id.country_id.code == 'MX'
            # as checked in '_is_required_for_invoice'
            cfdi_values["currency_conversion_rate"] = (
                abs(payslip.amount_total_signed) / abs(payslip.amount_total)
                if payslip.amount_total
                else 1
            )

        if cfdi_values["customer"].country_id.l10n_mx_edi_code != "MEX" and cfdi_values[
            "customer_rfc"
        ] not in ("XEXX010101000", "XAXX010101000"):
            cfdi_values["customer_fiscal_residence"] = cfdi_values[
                "customer"
            ].country_id.l10n_mx_edi_code
        else:
            cfdi_values["customer_fiscal_residence"] = None

        # ==== payslip lines ====

        cfdi_values["payslip_line_allowance_values"] = []
        cfdi_values["payslip_line_deduction_values"] = []
        cfdi_values["payslip_line_ImpuestosRetenidos_values"] = []
        cfdi_values["payslip_line_others_values"] = []

        for line in payslip_lines:
            if line.category_id.code == "ALW":
                cfdi_values["payslip_line_allowance_values"].append(
                    self._l10n_mx_hr_payroll_edi_get_payslip_line_cfdi_values(
                        payslip, line
                    )
                )
            if line.category_id.code == "DED" and line.total != 0.00:
                cfdi_values["payslip_line_deduction_values"].append(
                    self._l10n_mx_hr_payroll_edi_get_payslip_line_cfdi_values(
                        payslip, line
                    )
                )
            if (
                line.category_id.code == "DED"
                and line.total != 0.00
                and line.code in ("D045")
            ):
                cfdi_values["payslip_line_ImpuestosRetenidos_values"].append(
                    self._l10n_mx_hr_payroll_edi_get_payslip_line_cfdi_values(
                        payslip, line
                    )
                )
            if line.category_id.code == "OTPAY":
                cfdi_values["payslip_line_others_values"].append(
                    self._l10n_mx_hr_payroll_edi_get_payslip_line_cfdi_values(
                        payslip, line
                    )
                )

        # ==== Totals ====

        cfdi_values["total_allowance_amount"] = sum(
            vals["line"].total for vals in cfdi_values["payslip_line_allowance_values"]
        )
        cfdi_values["total_deduction_amount"] = sum(
            vals["line"].total for vals in cfdi_values["payslip_line_deduction_values"]
        )
        cfdi_values["TotalImpuestosRetenidos"] = sum(
            vals["line"].total
            for vals in cfdi_values["payslip_line_ImpuestosRetenidos_values"]
        )
        cfdi_values["TotalOtrasDeducciones"] = (
            cfdi_values["total_deduction_amount"]
            - cfdi_values["TotalImpuestosRetenidos"]
        )
        cfdi_values["total_others_amount"] = sum(
            vals["line"].total for vals in cfdi_values["payslip_line_others_values"]
        )
        cfdi_values["ValorUnitario_total"] = cfdi_values["total_allowance_amount"]
        cfdi_values["total_cfdi"] = (
            cfdi_values["total_allowance_amount"]
            - (cfdi_values["total_deduction_amount"])
        )

        return cfdi_values

    def _l10n_mx_hr_payroll_edi_get_templates(self):
        return "l10n_mx_hr_payroll_edi.cfdiv12", "nomina12.xsd"

    def _l10n_mx_hr_payroll_edi_export_payslip_cfdi(self, payslip):
        # == CFDI values ==
        cfdi_values = self._l10n_mx_hr_payroll_edi_get_payslip_cfdi_values(payslip)
        (
            qweb_template,
            xsd_attachment_name,
        ) = self._l10n_mx_hr_payroll_edi_get_templates()

        # == Generate the CFDI ==
        cfdi = self.env["ir.qweb"]._render(qweb_template, cfdi_values)
        decoded_cfdi_values = payslip._l10n_mx_hr_payroll_edi_decode_cfdi(
            cfdi_data=cfdi
        )
        cfdi_cadena_crypted = (
            cfdi_values["certificate"]
            .sudo()
            ._get_encrypted_cadena(decoded_cfdi_values["cadena"])
        )
        decoded_cfdi_values["cfdi_node"].attrib["Sello"] = cfdi_cadena_crypted

        res = {
            "cfdi_str": etree.tostring(
                decoded_cfdi_values["cfdi_node"],
                pretty_print=True,
                xml_declaration=True,
                encoding="UTF-8",
            ),
        }

        try:
            (
                self.env["ir.attachment"].l10n_mx_edi_validate_xml_from_attachment(
                    decoded_cfdi_values["cfdi_node"], xsd_attachment_name
                )
            )
        except UserError as error:
            res["errors"] = str(error).split("\\n")

        return res

    # --------------------------------------------------------------------------
    # CFDI: PACs
    # --------------------------------------------------------------------------

    def _l10n_mx_hr_payroll_edi_get_finkok_credentials(self, payslip):
        return self._l10n_mx_edi_get_finkok_credentials_company(payslip.company_id)

    def _l10n_mx_hr_payroll_edi_get_finkok_credentials_company(self, company):
        """Return the company credentials for PAC: finkok. Does not depend on a recordset"""
        if company.l10n_mx_hr_payroll_edi_pac_test_env:
            return {
                "username": "cfdi@vauxoo.com",
                "password": "vAux00__",
                "sign_url": "http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl",
                "cancel_url": "http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl",
            }
        else:
            if (
                not company.l10n_mx_hr_payroll_edi_pac_username
                or not company.l10n_mx_hr_payroll_edi_pac_password
            ):
                return {"errors": [_("The username and/or password are missing.")]}

            return {
                "username": company.l10n_mx_hr_payroll_edi_pac_username,
                "password": company.l10n_mx_hr_payroll_edi_pac_password,
                "sign_url": "http://facturacion.finkok.com/servicios/soap/stamp.wsdl",
                "cancel_url": "http://facturacion.finkok.com/servicios/soap/cancel.wsdl",
            }

    def _l10n_mx_hr_payroll_edi_finkok_sign(self, move, credentials, cfdi):
        return self._l10n_mx_hr_payroll_edi_finkok_sign_service(credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_finkok_sign_service(self, credentials, cfdi):
        """Send the CFDI XML document to Finkok for signature. Does not depend on a recordset"""
        try:
            transport = Transport(timeout=20)
            client = Client(credentials["sign_url"], transport=transport)
            response = client.service.stamp(
                cfdi, credentials["username"], credentials["password"]
            )
        except Exception as e:
            return {
                "errors": [
                    _(
                        "The Finkok service failed to sign with the following error: %s",
                        str(e),
                    )
                ],
            }

        if response.Incidencias and not response.xml:
            code = getattr(response.Incidencias.Incidencia[0], "CodigoError", None)
            msg = getattr(response.Incidencias.Incidencia[0], "MensajeIncidencia", None)
            errors = []
            if code:
                errors.append(_("Code : %s") % code)
            if msg:
                errors.append(_("Message : %s") % msg)
            return {"errors": errors}

        cfdi_signed = getattr(response, "xml", None)
        if cfdi_signed:
            cfdi_signed = cfdi_signed.encode("utf-8")

        return {
            "cfdi_signed": cfdi_signed,
            "cfdi_encoding": "str",
        }

    def _l10n_mx_hr_payroll_edi_finkok_cancel(self, payslip, credentials, cfdi):
        uuid_replace = payslip.l10n_mx_edi_cancel_invoice_id.l10n_mx_edi_cfdi_uuid
        return self._l10n_mx_hr_payroll_edi_finkok_cancel_service(
            payslip.l10n_mx_edi_cfdi_uuid,
            payslip.company_id,
            credentials,
            uuid_replace=uuid_replace,
        )

    def _l10n_mx_hr_payroll_edi_finkok_cancel_service(
        self, uuid, company, credentials, uuid_replace=None
    ):
        """Cancel the CFDI document with PAC: finkok. Does not depend on a recordset"""
        certificates = company.l10n_mx_hr_payroll_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        cer_pem = certificate.get_pem_cer(certificate.content)
        key_pem = certificate.get_pem_key(certificate.key, certificate.password)
        try:
            transport = Transport(timeout=20)
            client = Client(credentials["cancel_url"], transport=transport)
            factory = client.type_factory("apps.services.soap.core.views")
            uuid_type = factory.UUID()
            uuid_type.UUID = uuid
            uuid_type.Motivo = "01" if uuid_replace else "02"
            if uuid_replace:
                uuid_type.FolioSustitucion = uuid_replace
            docs_list = factory.UUIDArray(uuid_type)
            response = client.service.cancel(
                docs_list,
                credentials["username"],
                credentials["password"],
                company.vat,
                cer_pem,
                key_pem,
            )
        except Exception as e:
            return {
                "errors": [
                    _(
                        "The Finkok service failed to cancel with the following error: %s",
                        str(e),
                    )
                ],
            }

        if not getattr(response, "Folios", None):
            code = getattr(response, "CodEstatus", None)
            msg = (
                _("Cancelling got an error")
                if code
                else _("A delay of 2 hours has to be respected before to cancel")
            )
        else:
            code = getattr(response.Folios.Folio[0], "EstatusUUID", None)
            cancelled = code in ("201", "202")  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            code = "" if cancelled else code
            msg = "" if cancelled else _("Cancelling got an error")

        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        if errors:
            return {"errors": errors}

        return {"success": True}

    def _l10n_mx_hr_payroll_edi_finkok_sign_payslip(self, payslip, credentials, cfdi):
        return self._l10n_mx_hr_payroll_edi_finkok_sign(payslip, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_finkok_cancel_payslip(self, payslip, credentials, cfdi):
        return self._l10n_mx_hr_payroll_edi_finkok_cancel(payslip, credentials, cfdi)

    # Solucion Factible
    def _l10n_mx_hr_payroll_edi_get_solfact_credentials(self, payslip):
        return self._l10n_mx_hr_payroll_edi_get_solfact_credentials_company(
            payslip.company_id
        )

    def _l10n_mx_hr_payroll_edi_get_solfact_credentials_company(self, company):
        """Return the company credentials for PAC: solucion factible.
        Does not depend on a recordset"""
        if company.l10n_mx_hr_payroll_edi_pac_test_env:
            return {
                "username": "testing@solucionfactible.com",
                "password": "timbrado.SF.16672",
                "url": "https://testing.solucionfactible.com/ws/services/Timbrado?wsdl",
            }
        else:
            if (
                not company.l10n_mx_hr_payroll_edi_pac_username
                or not company.l10n_mx_hr_payroll_edi_pac_password
            ):
                return {"errors": [_("The username and/or password are missing.")]}

            return {
                "username": company.l10n_mx_hr_payroll_edi_pac_username,
                "password": company.l10n_mx_hr_payroll_edi_pac_password,
                "url": "https://solucionfactible.com/ws/services/Timbrado?wsdl",
            }

    def _l10n_mx_hr_payroll_edi_solfact_sign(self, payslip, credentials, cfdi):
        return self._l10n_mx_hr_payroll_edi_solfact_sign_service(credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_solfact_sign_service(self, credentials, cfdi):
        """Send the CFDI XML document to Solucion Factible for signature.
        Does not depend on a recordset"""
        try:
            transport = Transport(timeout=20)
            client = Client(credentials["url"], transport=transport)
            response = client.service.timbrar(
                credentials["username"], credentials["password"], cfdi, False
            )
        except Exception as e:
            return {
                "errors": [
                    _(
                        "The Solucion Factible service failed to sign with the "
                        "following error: %s",
                        str(e),
                    )
                ],
            }

        if response.status != 200:
            # ws-timbrado-timbrar - status 200:
            # CFDI correctamente validado y timbrado.
            return {
                "errors": [
                    _(
                        "The Solucion Factible service failed to sign with "
                        "the following error: %s",
                        response.mensaje,
                    )
                ],
            }

        res = response.resultados
        cfdi_signed = getattr(res[0] if res else response, "cfdiTimbrado", None)

        if cfdi_signed:
            return {
                "cfdi_signed": cfdi_signed,
                "cfdi_encoding": "str",
            }

        msg = getattr(res[0] if res else response, "mensaje", None)
        code = getattr(res[0] if res else response, "status", None)
        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        return {"errors": errors}

    def _l10n_mx_hr_payroll_edi_solfact_cancel(self, payslip, credentials, cfdi):
        uuid_replace = payslip.l10n_mx_edi_cancel_payslip_id.l10n_mx_edi_cfdi_uuid
        return self._l10n_mx_edi_solfact_cancel_service(
            payslip.l10n_mx_edi_cfdi_uuid,
            payslip.company_id,
            credentials,
            uuid_replace=uuid_replace,
        )

    def _l10n_mx_hr_payroll_edi_solfact_cancel_service(
        self, uuid, company, credentials, uuid_replace=None
    ):
        """calls the Solucion Factible web service to cancel the document based on the UUID.
        Method does not depend on a recordset
        """
        motivo = "01" if uuid_replace else "02"
        uuid = uuid + "|" + motivo + "|"
        if uuid_replace:
            uuid = uuid + uuid_replace
        certificates = company.l10n_mx_hr_payroll_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        cer_pem = certificate.get_pem_cer(certificate.content)
        key_pem = certificate.get_pem_key(certificate.key, certificate.password)
        key_password = certificate.password

        try:
            transport = Transport(timeout=20)
            client = Client(credentials["url"], transport=transport)
            response = client.service.cancelar(
                credentials["username"],
                credentials["password"],
                uuid,
                cer_pem,
                key_pem,
                key_password,
            )
        except Exception as e:
            return {
                "errors": [
                    _(
                        "The Solucion Factible service failed to cancel with "
                        "the following error: %s",
                        str(e),
                    )
                ],
            }

        if response.status not in (200, 201):
            # ws-timbrado-cancelar - status 200:
            # El proceso de cancelación se ha completado correctamente.
            # ws-timbrado-cancelar - status 201:
            # El folio se ha cancelado con éxito.
            return {
                "errors": [
                    _(
                        "The Solucion Factible service failed to cancel with "
                        "the following error: %s",
                        response.mensaje,
                    )
                ],
            }

        res = response.resultados
        code = (
            getattr(res[0], "statusUUID", None)
            if res
            else getattr(response, "status", None)
        )
        cancelled = code in ("201", "202")  # cancelled or previously cancelled
        # no show code and response message if cancel was success
        msg = "" if cancelled else getattr(res[0] if res else response, "mensaje", None)
        code = "" if cancelled else code

        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        if errors:
            return {"errors": errors}

        return {"success": True}

    def _l10n_mx_hr_payroll_edi_solfact_sign_payslip(self, payslip, credentials, cfdi):
        return self._l10n_mx_hr_payroll_edi_solfact_sign(payslip, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_solfact_cancel_payslip(
        self, payslip, credentials, cfdi
    ):
        return self._l10n_mx_hr_payroll_edi_solfact_cancel(payslip, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_get_sw_token(self, credentials):
        if credentials["password"] and not credentials["username"]:
            # token is configured directly instead of user/password
            return {
                "token": credentials["password"].strip(),
            }

        try:
            headers = {
                "user": credentials["username"],
                "password": credentials["password"],
                "Cache-Control": "no-cache",
            }
            response = requests.post(
                credentials["login_url"], headers=headers, timeout=3
            )
            response.raise_for_status()
            response_json = response.json()
            return {
                "token": response_json["data"]["token"],
            }
        except (requests.exceptions.RequestException, KeyError, TypeError) as req_e:
            return {
                "errors": [str(req_e)],
            }

    def _l10n_mx_hr_payroll_edi_get_sw_credentials(self, payslip):
        return self._l10n_mx_hr_payroll_edi_get_sw_credentials_company(
            payslip.company_id
        )

    def _l10n_mx_hr_payroll_edi_get_sw_credentials_company(self, company):
        """Get the company credentials for PAC: SW.
        Does not depend on a recordset"""
        if (
            not company.l10n_mx_hr_payroll_edi_pac_username
            or not company.l10n_mx_hr_payroll_edi_pac_password
        ):
            return {"errors": [_("The username and/or password are missing.")]}

        credentials = {
            "username": company.l10n_mx_hr_payroll_edi_pac_username,
            "password": company.l10n_mx_hr_payroll_edi_pac_password,
        }

        if company.l10n_mx_hr_payroll_edi_pac_test_env:
            credentials.update(
                {
                    "login_url": "https://services.test.sw.com.mx/security/authenticate",
                    "sign_url": "https://services.test.sw.com.mx/cfdi33/stamp/v3/b64",
                    "cancel_url": "https://services.test.sw.com.mx/cfdi33/cancel/csd",
                }
            )
        else:
            credentials.update(
                {
                    "login_url": "https://services.sw.com.mx/security/authenticate",
                    "sign_url": "https://services.sw.com.mx/cfdi33/stamp/v3/b64",
                    "cancel_url": "https://services.sw.com.mx/cfdi33/cancel/csd",
                }
            )

        # Retrieve a valid token.
        credentials.update(self._l10n_mx_hr_payroll_edi_get_sw_token(credentials))

        return credentials

    def _l10n_mx_hr_payroll_edi_sw_call(self, url, headers, payload=None):
        try:
            response = requests.post(
                url, data=payload, headers=headers, verify=True, timeout=20
            )
        except requests.exceptions.RequestException as req_e:
            return {"status": "error", "message": str(req_e)}
        msg = ""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as res_e:
            msg = str(res_e)
        try:
            response_json = response.json()
        except JSONDecodeError:
            # If it is not possible get json then
            # use response exception message
            return {"status": "error", "message": msg}
        if response_json["status"] == "error" and response_json["message"].startswith(
            "307"
        ):
            # XML signed previously
            cfdi = base64.encodebytes(response_json["messageDetail"].encode("UTF-8"))
            cfdi = cfdi.decode("UTF-8")
            response_json["data"] = {"cfdi": cfdi}
            # We do not need an error message if XML signed was
            # retrieved then cleaning them
            response_json.update(
                {
                    "message": None,
                    "messageDetail": None,
                    "status": "success",
                }
            )
        return response_json

    def _l10n_mx_hr_payroll_edi_sw_sign(self, payslip, credentials, cfdi):
        return self._l10n_mx_edi_sw_sign_service(credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_sw_sign_service(self, credentials, cfdi):
        """calls the SW web service to send and sign the CFDI XML.
        Method does not depend on a recordset
        """
        cfdi_b64 = base64.encodebytes(cfdi).decode("UTF-8")
        random_values = [
            random.choice(string.ascii_letters + string.digits) for n in range(30)
        ]
        boundary = "".join(random_values)
        payload = """--%(boundary)s
Content-Type: text/xml
Content-Transfer-Encoding: binary
Content-Disposition: form-data; name="xml"; filename="xml"
%(cfdi_b64)s
--%(boundary)s--
""" % {
            "boundary": boundary,
            "cfdi_b64": cfdi_b64,
        }
        payload = payload.replace("\n", "\r\n").encode("UTF-8")

        headers = {
            "Authorization": "bearer " + credentials["token"],
            "Content-Type": ("multipart/form-data; " 'boundary="%s"') % boundary,
        }

        response_json = self._l10n_mx_hr_payroll_edi_sw_call(
            credentials["sign_url"], headers, payload=payload
        )

        try:
            cfdi_signed = response_json["data"]["cfdi"]
        except (KeyError, TypeError):
            cfdi_signed = None

        if cfdi_signed:
            return {
                "cfdi_signed": cfdi_signed.encode("UTF-8"),
                "cfdi_encoding": "base64",
            }
        else:
            code = response_json.get("message")
            msg = response_json.get("messageDetail")
            errors = []
            if code:
                errors.append(_("Code : %s") % code)
            if msg:
                errors.append(_("Message : %s") % msg)
            return {"errors": errors}

    def _l10n_mx_hr_payroll_edi_sw_cancel(self, payslip, credentials, cfdi):
        uuid_replace = payslip.l10n_mx_edi_cancel_invoice_id.l10n_mx_edi_cfdi_uuid
        return self._l10n_mx_hr_payroll_edi_sw_cancel_service(
            payslip.l10n_mx_edi_cfdi_uuid,
            payslip.company_id,
            credentials,
            uuid_replace=uuid_replace,
        )

    def _l10n_mx_hr_payroll_edi_sw_cancel_service(
        self, uuid, company, credentials, uuid_replace=None
    ):
        """Calls the SW web service to cancel the document based on the UUID.
        Method does not depend on a recordset
        """
        headers = {
            "Authorization": "bearer " + credentials["token"],
            "Content-Type": "application/json",
        }
        certificates = company.l10n_mx_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        payload_dict = {
            "rfc": company.vat,
            "b64Cer": certificate.content.decode("UTF-8"),
            "b64Key": certificate.key.decode("UTF-8"),
            "password": certificate.password,
            "uuid": uuid,
            "motivo": "01" if uuid_replace else "02",
        }
        if uuid_replace:
            payload_dict["folioSustitucion"] = uuid_replace
        payload = json.dumps(payload_dict)

        response_json = self._l10n_mx_hr_payroll_edi_sw_call(
            credentials["cancel_url"], headers, payload=payload.encode("UTF-8")
        )

        cancelled = response_json["status"] == "success"
        if cancelled:
            return {"success": cancelled}

        code = response_json.get("message")
        msg = response_json.get("messageDetail")
        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        return {"errors": errors}

    def _l10n_mx_hr_payroll_edi_sw_sign_payslip(self, payslip, credentials, cfdi):
        return self._l10n_mx_edi_sw_sign(payslip, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_sw_cancel_payslip(self, payslip, credentials, cfdi):
        return self._l10n_mx_edi_sw_cancel(payslip, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_sw_sign_payment(self, move, credentials, cfdi):
        return self._l10n_mx_edi_sw_sign(move, credentials, cfdi)

    def _l10n_mx_hr_payroll_edi_sw_cancel_payment(self, move, credentials, cfdi):
        return self._l10n_mx_edi_sw_cancel(move, credentials, cfdi)

    # -------------------------------------------------------------------------
    # BUSINESS FLOW: EDI
    # -------------------------------------------------------------------------

    def _post_payslip_edi(self, payslips, test_mode=False):
        edi_result = {}
        for payslip in payslips:
            # == Check the configuration ==
            errors = self._l10n_mx_hr_payroll_edi_check_configuration(payslip)
            if errors:
                edi_result[payslip] = {
                    "error": self._l10n_mx_hr_payroll_edi_format_error_message(
                        _("Invalid configuration:"), errors
                    ),
                }
                continue

            # == Generate the CFDI ==
            res = self._l10n_mx_hr_payroll_edi_export_payslip_cfdi(payslip)
            if res.get("errors"):
                edi_result[payslip] = {
                    "error": self._l10n_mx_hr_payroll_edi_format_error_message(
                        _("Failure during the generation of the CFDI:"), res["errors"]
                    ),
                }
                continue

            # == Call the web-service ==
            pac_name = payslip.company_id.l10n_mx_hr_payroll_edi_pac

            credentials = getattr(
                self, "_l10n_mx_hr_payroll_edi_get_%s_credentials" % pac_name
            )(payslip)
            if credentials.get("errors"):
                edi_result[payslip] = {
                    "error": self._l10n_mx_hr_payroll_edi_format_error_message(
                        _("PAC authentification error:"), credentials["errors"]
                    ),
                }
                continue

            res = getattr(self, "_l10n_mx_hr_payroll_edi_%s_sign_payslip" % pac_name)(
                payslip, credentials, res["cfdi_str"]
            )
            if res.get("errors"):
                edi_result[payslip] = {
                    "error": self._l10n_mx_edi_format_error_message(
                        _("PAC failed to sign the CFDI:"), res["errors"]
                    ),
                }
                continue

            if res["cfdi_encoding"] == "str":
                res.update(
                    {
                        "cfdi_signed": base64.encodebytes(res["cfdi_signed"]),
                        "cfdi_encoding": "base64",
                    }
                )

            # == Create the attachment ==
            cfdi_filename = ("%s-MX-payslip-1.2.xml" % (payslip.number)).replace(
                "/", ""
            )
            cfdi_attachment = self.env["ir.attachment"].create(
                {
                    "name": cfdi_filename,
                    "res_id": payslip.id,
                    "res_model": payslip._name,
                    "type": "binary",
                    "datas": res["cfdi_signed"],
                    "mimetype": "application/xml",
                    "description": _(
                        "Mexican payslip CFDI generated for the %s document."
                    )
                    % payslip.name,
                }
            )

            edi_result[payslip] = {"attachment": cfdi_attachment}
            # # == Chatter ==
            # payslip.with_context(no_new_payslip=True).message_post(
            #     body=_("The CFDI document was successfully created and
            #     signed by the government."),
            #     attachment_ids=cfdi_attachment.ids,
            # )
        return edi_result
