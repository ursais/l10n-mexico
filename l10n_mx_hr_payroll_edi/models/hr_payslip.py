import base64
import logging
from datetime import datetime

from lxml import etree
from lxml.objectify import fromstring
from pytz import timezone

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

_logger = logging.getLogger(__name__)
CFDI_XSLT_CADENA = "l10n_mx_edi_40/data/4.0/cadenaoriginal_4_0.xslt"
CFDI_XSLT_CADENA_TFD = "l10n_mx_edi_40/data/4.0/cadenaoriginal_TFD_1_1.xslt"


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    edi_document_ids = fields.One2many(
        comodel_name="payslip.edi.document", inverse_name="payslip_id"
    )
    edi_payroll_state = fields.Selection(
        selection=[
            ("to_send", "To Send"),
            ("sent", "Sent"),
            ("to_cancel", "To Cancel"),
            ("cancelled", "Cancelled"),
        ],
        string="Electronic Payroll",
        store=True,
        compute="_compute_edi_state",
        help="The aggregated state of all the EDIs with web-service of this payslip",
    )
    edi_payroll_error_count = fields.Integer(
        compute="_compute_edi_payroll_error_count",
        help="How many EDIs are in error for this payslip ?",
    )
    edi_payroll_blocking_level = fields.Selection(
        selection=[("info", "Info"), ("warning", "Warning"), ("error", "Error")],
        compute="_compute_edi_payroll_error_message",
    )
    edi_payroll_error_message = fields.Html(
        compute="_compute_edi_payroll_error_message"
    )
    edi_payroll_web_services_to_process = fields.Text(
        compute="_compute_edi_payroll_web_services_to_process"
    )
    edi_payroll_show_cancel_button = fields.Boolean(
        compute="_compute_edi_payroll_show_cancel_button"
    )
    edi_payroll_show_abandon_cancel_button = fields.Boolean(
        compute="_compute_edi_show_abandon_cancel_button"
    )

    # ==== CFDI flow fields ====

    l10n_mx_edi_state_pac = fields.Selection(
        selection=[
            ("no_signed", "No Signed"),
            ("signed", "Signed"),
        ],
        string="PAC Status",
        store=False,
        compute="_compute_cfdi_values",
        help="Flag indicating a CFDI should be generated for this journal entry.",
    )

    l10n_mx_edi_cfdi_request = fields.Selection(
        selection=[
            ("on_payslip", "On payslip"),
            ("on_refund", "On Credit Note"),
            ("on_payment", "On Payment"),
        ],
        string="Request a CFDI",
        store=True,
        compute="_compute_l10n_mx_edi_cfdi_request",
        help="Flag indicating a CFDI should be generated for this journal entry.",
    )

    l10n_mx_edi_stamp_status = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("error", "Error"),
            ("stamped", "Stamped"),
        ],
        string="Stamp status",
        readonly=True,
        copy=False,
        required=True,
        default="draft",
        help="",
    )

    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ("none", "State not defined"),
            ("undefined", "Not Synced Yet"),
            ("not_found", "Not Found"),
            ("cancelled", "Cancelled"),
            ("valid", "Valid"),
        ],
        string="SAT status",
        readonly=True,
        copy=False,
        required=True,
        tracking=True,
        default="undefined",
        help="Refers to the status of the journal entry inside the SAT system.",
    )

    l10n_mx_edi_post_time = fields.Datetime(
        string="Posted Time",
        readonly=True,
        copy=False,
        help="Keep empty to use the current México central time",
    )

    l10n_mx_edi_origin = fields.Char(
        string="CFDI Origin",
        copy=False,
        help="In some cases like payments, credit notes, debit notes, invoices "
        "re-signed or invoices that are redone due to payment in advance "
        "will need this field filled, the format is:\n"
        "Origin Type|UUID1, UUID2, ...., UUIDn.\n"
        "Where the origin type could be:\n"
        "- 01: Credit Note\n"
        "- 02: Debit note for related documents\n"
        "- 03: Return of merchandise on previous invoices or shipments\n"
        "- 04: Replacement of previous CFDIs\n"
        "- 05: Previously invoiced merchandise shipments\n"
        "- 06: Invoice generated for previous shipments\n"
        "- 07: CFDI for advance application",
    )

    l10n_mx_edi_cancel_payslip_id = fields.Many2one(
        comodel_name="hr.payslip",
        string="Substituted By",
        compute="_compute_l10n_mx_edi_cancel",
        readonly=True,
    )
    l10n_mx_edi_cfdi_uuid = fields.Char(
        string="Fiscal Folio",
        copy=False,
        readonly=True,
        help="Folio in electronic invoice, is returned by SAT when send to stamp.",
        compute="_compute_cfdi_values",
    )
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char(
        string="Supplier RFC",
        copy=False,
        readonly=True,
        help="The supplier tax identification number.",
        compute="_compute_cfdi_values",
    )
    l10n_mx_edi_cfdi_customer_rfc = fields.Char(
        string="Customer RFC",
        copy=False,
        readonly=True,
        help="The customer tax identification number.",
        compute="_compute_cfdi_values",
    )
    l10n_mx_edi_cfdi_amount = fields.Monetary(
        string="Total Amount",
        copy=False,
        readonly=True,
        help="The total amount reported on the cfdi.",
        compute="_compute_cfdi_values",
    )

    # ==== Other fields ====

    l10n_mx_edi_payment_method_id = fields.Many2one(
        "l10n_mx_edi.payment.method",
        string="Payment Way",
        help="Indicates the way the invoice was/will be paid, "
        "where the options could be: "
        "Cash, Nominal Check, Credit Card, etc. "
        "Leave empty if unkown and the XML will show 'Unidentified'.",
        default=lambda self: self.env.ref(
            "l10n_mx_edi.payment_method_otros", raise_if_not_found=False
        ),
    )

    l10n_mx_edi_payment_policy = fields.Selection(
        string="Payment Policy",
        selection=[("PPD", "PPD"), ("PUE", "PUE")],
        compute="_compute_l10n_mx_edi_payment_policy",
    )

    uso_cfdi = fields.Selection(
        selection=[("P01", "Por definir")],
        string="Uso CFDI (Employee)",
        default="P01",
    )

    @api.depends("edi_document_ids.state")
    def _compute_edi_state(self):
        for payslip in self:
            all_states = set(
                payslip.edi_document_ids.filtered(
                    lambda d: d.edi_format_id._needs_web_services()
                ).mapped("state")
            )
            if all_states == {"sent"}:
                payslip.edi_payroll_state = "sent"
            elif all_states == {"cancelled"}:
                payslip.edi_payroll_state = "cancelled"
            elif "to_send" in all_states:
                payslip.edi_payroll_state = "to_send"
            elif "to_cancel" in all_states:
                payslip.edi_payroll_state = "to_cancel"
            else:
                payslip.edi_payroll_state = False

    @api.depends("edi_document_ids.error")
    def _compute_edi_error_count(self):
        for payslip in self:
            payslip.edi_payroll_error_count = len(
                payslip.edi_document_ids.filtered(lambda d: d.error)
            )

    @api.depends(
        "edi_payroll_error_count",
        "edi_document_ids.error",
        "edi_payroll_blocking_level",
    )
    def _compute_edi_payroll_error_message(self):
        for payslip in self:
            if payslip.edi_payroll_error_count == 0:
                payslip.edi_payroll_error_message = None
                payslip.edi_payroll_blocking_level = None
            elif payslip.edi_payroll_error_count == 1:
                error_doc = payslip.edi_payroll_document_ids.filtered(lambda d: d.error)
                payslip.edi_payroll_error_message = error_doc.error
                payslip.edi_payroll_blocking_level = (
                    error_doc.edi_payroll_blocking_level
                )
            else:
                error_levels = {
                    doc.edi_payroll_blocking_level for doc in payslip.edi_document_ids
                }
                if "error" in error_levels:
                    payslip.edi_payroll_error_message = str(
                        payslip.edi_payroll_error_count
                    ) + _(" Electronic Payslip error(s)")
                    payslip.edi_payroll_blocking_level = "error"
                elif "warning" in error_levels:
                    payslip.edi_payroll_error_message = str(
                        payslip.edi_payroll_error_count
                    ) + _(" Electronic Payslip warning(s)")
                    payslip.edi_payroll_blocking_level = "warning"
                else:
                    payslip.edi_payroll_error_message = str(
                        payslip.edi_payroll_error_count
                    ) + _(" Electronic Payslip info(s)")
                    payslip.edi_payroll_blocking_level = "info"

    @api.depends(
        "edi_document_ids",
        "edi_document_ids.state",
        "edi_document_ids.edi_payroll_blocking_level",
        "edi_document_ids.edi_format_id",
        "edi_document_ids.edi_format_id.name",
    )
    def _compute_edi_web_services_to_process(self):
        for payslip in self:
            to_process = payslip.edi_document_ids.filtered(
                lambda d: d.state in ["to_send", "to_cancel"]
                and d.blocking_level != "error"
            )
            format_web_services = to_process.edi_format_id.filtered(
                lambda f: f._needs_web_services()
            )
            payslip.edi_web_services_to_process = ", ".join(
                f.name for f in format_web_services
            )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_get_cadena_xslts(self):
        return CFDI_XSLT_CADENA_TFD, CFDI_XSLT_CADENA

    # --------------------------------------------------------------------------
    # Payroll slip buttons
    # --------------------------------------------------------------------------

    def action_stamp_payroll_pac(self):
        if self.journal_id.edi_format_ids.code != "cfdi_1_2":
            return super().action_payslip_done()
        certificate_date = (
            self.env["l10n_mx_edi.certificate"].sudo().get_mx_current_datetime()
        )

        edi_document_vals_list = []

        for payslip in self:
            _logger.info("action_stamp_payroll_pac  --->>>   " + str(payslip.number))
            if payslip.l10n_mx_edi_state_pac == "no_signed":
                issued_address = payslip._get_l10n_mx_hr_payroll_edi_issued_address()
                tz = self._l10n_mx_edi_get_cfdi_partner_timezone(issued_address)
                tz_force = (
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param(
                        "l10n_mx_edi_tz_%s" % payslip.journal_id.id, default=None
                    )
                )
                if tz_force:
                    tz = timezone(tz_force)
                payslip.l10n_mx_edi_post_time = fields.Datetime.to_string(
                    datetime.now(tz)
                )

                if payslip.l10n_mx_edi_cfdi_request in ("on_payslip"):
                    # Assign time and date coming from a certificate.
                    if not payslip.payslip_date:
                        payslip.payslip_date = certificate_date.date()
                    # payslip.with_context(check_move_validity=False)._onchange_payslip_date()
                edi_result = self.env["account.edi.format"]._post_payslip_edi(payslip)
                if edi_result[payslip].get("error", False):
                    raise UserError(
                        _("Invalid payslip configuration:\n\n%s")
                        % (edi_result[payslip].get("error", False))
                    )
                payslip.l10n_mx_edi_stamp_status = "stamped"
                for edi_format in payslip.journal_id.edi_format_ids:
                    is_edi_needed = True

                    if is_edi_needed:
                        errors = edi_format._check_move_configuration(payslip)
                        if errors:
                            raise UserError(
                                _("Invalid payslip configuration:\n\n%s")
                                % "\n".join(errors)
                            )

                        existing_edi_document = payslip.edi_document_ids.filtered(
                            lambda x, y=edi_format: x.edi_format_id == y
                        )
                        if existing_edi_document:
                            _logger.warning("existing_edi_document")
                        attachment_xml = self.env["ir.attachment"].search(
                            [
                                ("name", "like", "-MX-payslip-1.2.xml"),
                                ("res_id", "=", payslip.id),
                            ]
                        )
                        if existing_edi_document:
                            existing_edi_document.write(
                                {
                                    "state": "to_send",
                                    "attachment_id": attachment_xml.id
                                    if attachment_xml
                                    else False,
                                }
                            )
                        else:
                            payslip_id = payslip.id
                            edi_document_vals_list = {
                                "edi_format_id": edi_format.id,
                                "payslip_id": payslip_id,
                                "state": "to_send",
                                "attachment_id": attachment_xml.id
                                if attachment_xml
                                else False,
                            }
                            self.env["payslip.edi.document"].create(
                                edi_document_vals_list
                            )

            # Validate work entries for regular payslips
            # (exclude end of year bonus, ...)
        else:
            _logger.info("CFDI stamped before   --->>>  " + str(payslip.number))
            payslip.message_post(
                body=_(
                    "CFDI stamped before - payslip number: %(msg)s",
                    msg=str(payslip.number),
                )
            )

        return

    def _get_l10n_mx_hr_payroll_edi_issued_address(self):
        self.ensure_one()
        return self.company_id.partner_id.commercial_partner_id

    @api.model
    def _l10n_mx_edi_get_cfdi_partner_timezone(self, partner):
        code = partner.state_id.code

        # northwest area
        if code == "BCN":
            return timezone("America/Tijuana")
        # Southeast area
        elif code == "ROO":
            return timezone("America/Cancun")
        # Pacific area
        elif code in ("BCS", "CHH", "SIN", "NAY"):
            return timezone("America/Chihuahua")
        # Sonora
        elif code == "SON":
            return timezone("America/Hermosillo")
        # By default, takes the central area timezone
        return timezone("America/Mexico_City")

    def _compute_l10n_mx_edi_cancel(self):
        for move in self:
            if move.l10n_mx_edi_cfdi_uuid:
                replaced_move = move.search(
                    [
                        ("l10n_mx_edi_origin", "like", "04|%"),
                        (
                            "l10n_mx_edi_origin",
                            "like",
                            "%" + move.l10n_mx_edi_cfdi_uuid + "%",
                        ),
                        ("company_id", "=", move.company_id.id),
                    ],
                    limit=1,
                )
                move.l10n_mx_edi_cancel_payslip_id = replaced_move
            else:
                move.l10n_mx_edi_cancel_payslip_id = None

    # -------------------------------------------------------------------------
    # SAT
    # -------------------------------------------------------------------------

    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the invoice is
        valid."""
        for payslip in self:
            supplier_rfc = payslip.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = payslip.l10n_mx_edi_cfdi_customer_rfc
            total = float_repr(
                payslip.l10n_mx_edi_cfdi_amount,
                precision_digits=payslip.currency_id.decimal_places,
            )
            uuid = payslip.l10n_mx_edi_cfdi_uuid
            try:
                status = self.env["account.edi.format"]._l10n_mx_edi_get_sat_status(
                    supplier_rfc, customer_rfc, total, uuid
                )
            except Exception as e:
                payslip.message_post(
                    body=_(
                        "Failure during update of the SAT status: %(msg)s", msg=str(e)
                    )
                )
                continue

            if status == "Vigente":
                payslip.l10n_mx_edi_sat_status = "valid"
            elif status == "Cancelado":
                payslip.l10n_mx_edi_sat_status = "cancelled"
            elif status == "No Encontrado":
                payslip.l10n_mx_edi_sat_status = "not_found"
            else:
                payslip.l10n_mx_edi_sat_status = "none"

    @api.model
    def _l10n_mx_payroll_edi_cron_update_sat_status(self):
        """Call the SAT to know if the invoice is available government-side or
        if the invoice has been cancelled.
        In the second case, the cancellation could be done Odoo-side and then
        we need to check if the SAT is up-to-date, or could be done manually
        government-side forcing Odoo to update the invoice's state.
        """

        # Update the 'l10n_mx_payroll_edi_sat_status' field.
        cfdi_edi_format = self.env.ref("l10n_mx_hr_payroll.edi_cfdi_payroll_1_2")
        to_process = self.env["payslip.edi.document"].search(
            [
                ("edi_format_id", "=", cfdi_edi_format.id),
                ("state", "in", ("sent", "cancelled")),
                (
                    "payslip_id.l10n_mx_edi_sat_status",
                    "in",
                    ("undefined", "not_found", "none"),
                ),
            ]
        )
        to_process.payslip_id.l10n_mx_edi_update_sat_status()

        # Handle the case when the invoice has been cancelled manually
        # government-side.
        to_process.filtered(
            lambda doc: doc.state == "sent"
            and doc.payslip_id.l10n_mx_edi_sat_status == "cancelled"
        ).payslip_id.action_payslip_cancel()

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends("company_id", "state")
    def _compute_l10n_mx_edi_cfdi_request(self):
        for payslip in self:
            payslip.l10n_mx_edi_state_pac = "no_signed"
            if payslip.country_code != "MX":
                payslip.l10n_mx_edi_cfdi_request = False
            else:
                payslip.l10n_mx_edi_cfdi_request = "on_payslip"

    @api.depends("payslip_date")
    def _compute_l10n_mx_edi_payment_policy(self):
        for payslip in self:
            payslip.l10n_mx_edi_payment_policy = False

    def compute_sheet(self):
        if self.journal_id.edi_format_ids.code != "cfdi_1_2":
            return super().action_payslip_done()
        payslips = self.filtered(lambda slip: slip.state in ["draft", "verify"])

        # delete old payslip lines
        payslips.line_ids.unlink()

        # Check if we have movements, loans and alimony
        for payslip in payslips:
            number = payslip.number or self.env["ir.sequence"].next_by_code(
                "salary.slip"
            )
            # payslip.calculate_imss()
            hr_payroll_movement_inputs = self.env["hr.payroll.movement.line"].search(
                [
                    ("date_start", "<=", payslip.date_from),
                    ("employee_id", "=", payslip.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )

            hr_payroll_movement_loans = self.env["hr.payroll.loan"].search(
                [
                    ("date_start", "<=", payslip.date_from),
                    ("employee_id", "=", payslip.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )

            hr_payroll_movement_alimony = self.env["hr.payroll.alimony"].search(
                [
                    ("date_start", "<=", payslip.date_from),
                    ("employee_id", "=", payslip.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )

            hr_payroll_movement_extratime = self.env[
                "hr.payroll.extratime.line"
            ].search(
                [
                    ("date", ">=", payslip.date_from),
                    ("date", "<=", payslip.date_to),
                    ("employee_id", "=", payslip.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )

            # Input Payroll Movements
            payslip.input_line_ids.unlink()
            for movement_input in hr_payroll_movement_inputs:
                payslip.input_line_ids.create(
                    {
                        "payslip_id": payslip.id,
                        "input_type_id": movement_input.payslip_input_id.id,
                        "amount": movement_input.amount,
                    }
                )

            # Input Payroll loans
            for loan in hr_payroll_movement_loans:
                payslip.input_line_ids.create(
                    {
                        "payslip_id": payslip.id,
                        "input_type_id": loan.loan_type_mx.id,
                        "amount": loan.amount,
                    }
                )

            # Input Payroll Alimony
            for alimony in hr_payroll_movement_alimony:
                payslip.input_line_ids.create(
                    {
                        "payslip_id": payslip.id,
                        "input_type_id": self.env.ref(
                            "l10n_mx_hr_payroll.input_alimony"
                        ).id,
                        "amount": alimony.amount,
                    }
                )

            # Input Payroll Extratime
            extratime_double = extratime_triple = 0
            for extra in hr_payroll_movement_extratime:
                if extra.type_hour == "double":
                    extratime_double += extra.hours
                if extra.type_hour == "triple":
                    extratime_triple += extra.hours

            if extratime_double > 0:
                payslip.input_line_ids.create(
                    {
                        "payslip_id": payslip.id,
                        "input_type_id": self.env.ref(
                            "l10n_mx_hr_payroll.input_extratime_double"
                        ).id,
                        "amount": extratime_double,
                    }
                )

            if extratime_triple > 0:
                payslip.input_line_ids.create(
                    {
                        "payslip_id": payslip.id,
                        "input_type_id": self.env.ref(
                            "l10n_mx_hr_payroll.input_extratime_triple"
                        ).id,
                        "amount": extratime_triple,
                    }
                )

            lines = [(0, 0, line) for line in payslip._get_payslip_lines()]

            payslip.write(
                {
                    "line_ids": lines,
                    "number": number,
                    "state": "verify",
                    "compute_date": fields.Date.today(),
                }
            )
        return True

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_l10n_mx_hr_payroll_edi_signed_edi_document(self):
        self.ensure_one()
        cfdi_1_2_edi = self.env.ref("l10n_mx_hr_payroll_edi.edi_cfdi_payroll_1_2")
        return self.edi_document_ids.filtered(
            lambda document: document.edi_format_id == cfdi_1_2_edi
            and document.attachment_id
        )

    def _l10n_mx_hr_payroll_edi_decode_cfdi(self, cfdi_data=None):
        self.ensure_one()

        # Find a signed cfdi.
        if not cfdi_data:
            signed_edi = self._get_l10n_mx_hr_payroll_edi_signed_edi_document()
            if signed_edi:
                cfdi_data = base64.decodebytes(
                    signed_edi.attachment_id.with_context(bin_size=False).datas
                )

        # Nothing to decode.
        if not cfdi_data:
            return {}

        try:
            cfdi_node = fromstring(cfdi_data)
        except etree.XMLSyntaxError:
            # Not an xml
            return {}

        return self._l10n_mx_edi_hr_payroll_decode_cfdi_etree(cfdi_node)

    def _l10n_mx_edi_hr_payroll_decode_cfdi_etree(self, cfdi_node):
        """Helper to extract relevant data from the CFDI etree object,
         does not require a move record.
        :param cfdi_node:   The cfdi etree object.
        :return:            A python dictionary.
        """

        def get_node(cfdi_node, attribute, namespaces):
            if hasattr(cfdi_node, "Complemento"):
                node = cfdi_node.Complemento.xpath(attribute, namespaces=namespaces)
                return node[0] if node else None
            else:
                return None

        def get_cadena(cfdi_node, template):
            if cfdi_node is None:
                return None
            cadena_root = etree.parse(tools.file_open(template))
            return str(etree.XSLT(cadena_root)(cfdi_node))

        tfd_node = get_node(
            cfdi_node,
            "tfd:TimbreFiscalDigital[1]",
            {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"},
        )

        return {
            "uuid": ({} if tfd_node is None else tfd_node).get("UUID"),
            "supplier_rfc": cfdi_node.Emisor.get("Rfc", cfdi_node.Emisor.get("rfc")),
            "customer_rfc": cfdi_node.Receptor.get(
                "Rfc", cfdi_node.Receptor.get("rfc")
            ),
            "amount_total": cfdi_node.get("Total", cfdi_node.get("total")),
            "cfdi_node": cfdi_node,
            "usage": cfdi_node.Receptor.get("UsoCFDI"),
            "payment_method": cfdi_node.get("formaDePago", cfdi_node.get("MetodoPago")),
            "bank_account": cfdi_node.get("NumCtaPago"),
            "sello": cfdi_node.get("sello", cfdi_node.get("Sello", "No identificado")),
            "sello_sat": tfd_node is not None
            and tfd_node.get("selloSAT", tfd_node.get("SelloSAT", "No identificado")),
            "cadena": tfd_node is not None
            and get_cadena(tfd_node, self._l10n_mx_edi_get_cadena_xslts()[0])
            or get_cadena(cfdi_node, self._l10n_mx_edi_get_cadena_xslts()[1]),
            "certificate_number": cfdi_node.get(
                "noCertificado", cfdi_node.get("NoCertificado")
            ),
            "certificate_sat_number": tfd_node is not None
            and tfd_node.get("NoCertificadoSAT"),
            "expedition": cfdi_node.get("LugarExpedicion"),
            "fiscal_regime": cfdi_node.Emisor.get("RegimenFiscal", ""),
            "emission_date_str": cfdi_node.get(
                "fecha", cfdi_node.get("Fecha", "")
            ).replace("T", " "),
            "stamp_date": tfd_node is not None
            and tfd_node.get("FechaTimbrado", "").replace("T", " "),
        }

    @api.model
    def _l10n_mx_edi_cfdi_amount_to_text(self):
        """Method to transform a float amount to text words
        E.g. 100 - ONE HUNDRED
        :returns: Amount transformed to words mexican format for invoices
        :rtype: str
        """
        self.ensure_one()

        currency_name = self.currency_id.name.upper()

        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = "M.N" if currency_name == "MXN" else "M.E."

        # Split integer and decimal part
        amount_i, amount_d = divmod(self.amount_total, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))

        words = (
            self.currency_id.with_context(
                lang=self.employee_id.address_home_id.lang or "es_ES"
            )
            .amount_to_text(amount_i)
            .upper()
        )
        return "%(words)s con %(amount_d)02d/100 %(currency_type)s" % {
            "words": words,
            "amount_d": amount_d,
            "currency_type": currency_type,
        }

    @api.model
    def _l10n_mx_edi_write_cfdi_origin(self, code, uuids):
        """Format the code and uuids passed as parameter in order to fill the
         l10n_mx_edi_origin field.
        The code corresponds to the following types:
            - 01: Nota de crédito
            - 02: Nota de débito de los documentos relacionados
            - 03: Devolución de mercancía sobre facturas o traslados previos
            - 04: Sustitución de los CFDI previos
            - 05: Traslados de mercancias facturados previamente
            - 06: Factura generada por los traslados previos
            - 07: CFDI por aplicación de anticipo
        The generated string must match the following template:
        <code>|<uuid1>,<uuid2>,...,<uuidn>
        :param code:    A valid code as a string between 01 and 07.
        :param uuids:   A list of uuids returned by the government.
        :return:        A valid string to be put inside the l10n_mx_edi_origin field.
        """
        return "%s|%s" % (code, ",".join(uuids))

    @api.model
    def _l10n_mx_edi_read_cfdi_origin(self, cfdi_origin):
        splitted = cfdi_origin.split("|")
        if len(splitted) != 2:
            return False

        try:
            code = int(splitted[0])
        except ValueError:
            return False

        if code < 1 or code > 7:
            return False
        return splitted[0], [uuid.strip() for uuid in splitted[1].split(",")]

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends("edi_document_ids")
    def _compute_cfdi_values(self):
        """Fill the invoice fields from the cfdi values."""
        for payslip in self:
            cfdi_infos = payslip._l10n_mx_hr_payroll_edi_decode_cfdi()
            _logger.info("_compute_cfdi_values  --->>  " + str(cfdi_infos))
            if cfdi_infos.get("uuid"):
                payslip.l10n_mx_edi_state_pac = "signed"
            else:
                payslip.l10n_mx_edi_state_pac = "no_signed"
            payslip.l10n_mx_edi_cfdi_uuid = cfdi_infos.get("uuid")
            payslip.l10n_mx_edi_cfdi_supplier_rfc = cfdi_infos.get("supplier_rfc")
            payslip.l10n_mx_edi_cfdi_customer_rfc = cfdi_infos.get("customer_rfc")
            payslip.l10n_mx_edi_cfdi_amount = cfdi_infos.get("amount_total")
