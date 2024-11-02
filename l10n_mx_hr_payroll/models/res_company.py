import base64
import logging
from os.path import join

import requests
from lxml import etree, objectify
from werkzeug.urls import url_quote

from odoo import SUPERUSER_ID, api, fields, models, tools

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    hr_payroll_employer_registers = fields.One2many(
        "hr.payroll.employer_register", "company_id", string="Employer Register"
    )

    hr_payroll_smg_l10n_mx = fields.Many2one("hr.payroll.ms", string="SMG")
    hr_payroll_uma_l10n_mx = fields.Many2one("hr.payroll.uma", string="UMA")
    hr_payroll_umi_l10n_mx = fields.Many2one("hr.payroll.umi", string="UMI")
    hr_payroll_settlement_structure_l10n_mx = fields.Many2one(
        "hr.payroll.structure", string="Structure"
    )

    @api.model
    def _load_xsd_attachments_for_payroll(self):
        url = "http://www.sat.gob.mx/sitio_internet/cfd/nomina/nomina12.xsd"
        xml_ids = self.env["ir.model.data"].search([("name", "like", "xsd_cached_%")])
        _logger.info("xml_ids", xml_ids)
        xsd_files = ["%s.%s" % (x.module, x.name) for x in xml_ids]
        _logger.info("xsd_files", xsd_files)
        for xsd in xsd_files:
            self.env.ref(xsd).unlink()
        self._load_xsd_files(url)

    @api.model
    def _load_xsd_files(self, url):
        fname = url.split("/")[-1]
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.getLogger(__name__).info("I cannot connect with the given URL.")
            return ""
        try:
            res = objectify.fromstring(response.content)
        except etree.XMLSyntaxError as e:
            logging.getLogger(__name__).info(
                "You are trying to load an invalid xsd file.\n%s", e
            )
            return ""
        namespace = {"xs": "http://www.w3.org/2001/XMLSchema"}
        if fname == "cfdv40.xsd":
            # This is the xsd root
            res = self._load_xsd_complements(res)
        sub_urls = res.xpath("//xs:import", namespaces=namespace)
        for s_url in sub_urls:
            s_url_catch = self._load_xsd_files(s_url.get("schemaLocation"))
            s_url.attrib["schemaLocation"] = url_quote(s_url_catch)
        try:
            xsd_string = etree.tostring(res, pretty_print=True)
        except etree.XMLSyntaxError:
            logging.getLogger(__name__).info("XSD file downloaded is not valid")
            return ""
        if not xsd_string:
            logging.getLogger(__name__).info("XSD file downloaded is empty")
            return ""
        env = api.Environment(self._cr, SUPERUSER_ID, {})
        xsd_fname = "xsd_cached_%s" % fname.replace(".", "_")
        attachment = env.ref("l10n_mx_edi.%s" % xsd_fname, False)
        filestore = tools.config.filestore(self._cr.dbname)
        if attachment:
            return join(filestore, attachment.store_fname)
        attachment = env["ir.attachment"].create(
            {
                "name": xsd_fname,
                "datas": base64.encodebytes(xsd_string),
            }
        )
        # Forcing the triggering of the store_fname
        attachment._inverse_datas()
        self._cr.execute(
            """INSERT INTO ir_model_data
            (name, res_id, module, model, noupdate)
            VALUES (%s, %s, 'l10n_mx_edi', 'ir.attachment', true)""",
            (xsd_fname, attachment.id),
        )
        return join(filestore, attachment.store_fname)
