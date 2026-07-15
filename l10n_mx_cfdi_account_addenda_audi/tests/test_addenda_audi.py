# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaAudi(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_edi_addenda_audi.l10n_mx_edi_addenda_audi"
        )
        cls.customer.write(
            {
                "l10n_mx_edi_addenda": cls.addenda_view.id,
                "audi_supplier_email": "supplier@audi.test",
                "audi_supplier_number": "SUP-001",
            }
        )
        cls.cfdi_product.product_tmpl_id.audi_ref = "AUDI-PART-123"

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Audi")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Audi")

    def test_audi_flag_compute(self):
        invoice = self._create_cfdi_invoice()
        self.assertTrue(invoice.audi_flag)
        partner_no_addenda = self.env["res.partner"].create(
            {"name": "No Addenda", "country_id": self.env.ref("base.mx").id}
        )
        invoice.partner_id = partner_no_addenda
        self.assertFalse(invoice.audi_flag)

    def test_product_audi_ref_onchange(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        line.audi_product_ref = False
        line.product_id = self.cfdi_product
        line._onchange_product_id_audi_ref()
        self.assertEqual(line.audi_product_ref, "AUDI-PART-123")

    def test_product_audi_ref_onchange_without_ref(self):
        product = self.env["product.product"].create(
            {
                "name": "No Audi Ref",
                "list_price": 10.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
            }
        )
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        line.audi_product_ref = "KEEP"
        line.product_id = product
        line._onchange_product_id_audi_ref()
        self.assertEqual(line.audi_product_ref, "KEEP")

    def test_render_audi_addenda_via_framework(self):
        invoice = self._create_cfdi_invoice(
            ref="PO-42",
            audi_business_unit="BU1",
            audi_applicant_email="applicant@audi.test",
            audi_tax_code="IVA16",
            audi_fiscal_document_type="FA",
            audi_document_type="INVOICE",
        )
        invoice.invoice_line_ids[0].audi_product_ref = "AUDI-PART-123"
        # SAMPLE CFDI-like bytes minimal for append helper
        sample = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Version="4.0">'
            b"</cfdi:Comprobante>"
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            sample, self.addenda_view
        )
        self.assertIn(b"AUDI-PART-123", result)
        self.assertIn(b"SUP-001", result)
        self.assertIn(b"supplier@audi.test", result)
        self.assertIn(b"PO-42", result)
        self.assertIn(b"applicant@audi.test", result)
        self.assertIn(b"Addenda", result)
