import base64
from unittest.mock import patch

from lxml import etree

from odoo.tests import tagged

from .common import ACTIVE_CFDI_RESPONSE, SAMPLE_CFDI_XML, CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestCFDIAddenda(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addenda_view = cls.env["ir.ui.view"].create(
            {
                "name": "Addenda Test",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": True,
                "arch": """
                    <data>
                        <test:AddendaTest xmlns:test="http://example.com/test">
                            <test:Value t-esc="record.name"/>
                        </test:AddendaTest>
                    </data>
                """,
            }
        )
        cls.customer.country_id = cls.env.ref("base.mx")
        cls.customer.l10n_mx_edi_addenda = cls.addenda_view
        # ACTIVE_CFDI_RESPONSE may omit Version; addenda append needs it.
        xml = ACTIVE_CFDI_RESPONSE["xml"]
        if b'Version="' not in xml:
            xml = xml.replace(
                b"<cfdi:Comprobante ",
                b'<cfdi:Comprobante Version="4.0" ',
                1,
            )
        cls._addenda_cfdi_response = {**ACTIVE_CFDI_RESPONSE, "xml": xml}

    def _mock_cfdi_publish(self):
        return patch.object(
            type(self.service),
            "create_cfdi",
            return_value=self._addenda_cfdi_response,
        )

    def test_partner_addenda_domain_lists_flagged_views_only(self):
        other = self.env["ir.ui.view"].create(
            {
                "name": "Not an addenda",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": False,
                "arch": "<data><span/></data>",
            }
        )
        field = self.env["res.partner"]._fields["l10n_mx_edi_addenda"]
        domain = field.domain
        matching = self.env["ir.ui.view"].search(domain)
        self.assertIn(self.addenda_view, matching)
        self.assertNotIn(other, matching)

    def test_append_addenda_wraps_content_in_cfdi_addenda(self):
        invoice = self._create_cfdi_invoice()
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            SAMPLE_CFDI_XML, self.addenda_view
        )
        root = etree.fromstring(result)
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4", "test": "http://example.com/test"}
        addenda = root.find("cfdi:Addenda", namespaces=ns)
        self.assertIsNotNone(addenda)
        self.assertIsNotNone(addenda.find("test:AddendaTest", namespaces=ns))

    def test_create_invoice_cfdi_stores_addenda_in_xml(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with self._mock_cfdi_publish():
            invoice.create_invoice_cfdi()
        document = invoice.cfdi_document_id
        self.assertTrue(document.xml_file)
        xml = base64.b64decode(document.xml_file)
        self.assertIn(b"Addenda", xml)
        self.assertIn(b"AddendaTest", xml)
        self.assertIn(invoice.name.encode(), xml)

    def test_create_refund_cfdi_stores_addenda_in_xml(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.action_post()
        with self._mock_cfdi_publish():
            refund.create_refund_cfdi()
        document = refund.related_cert_ids.filtered(
            lambda d: d.type == "E" and d.state == "published"
        )[:1]
        self.assertTrue(document)
        xml = base64.b64decode(document.xml_file)
        self.assertIn(b"Addenda", xml)
        self.assertIn(b"AddendaTest", xml)
