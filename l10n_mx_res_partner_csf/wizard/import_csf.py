import base64
import os

import pytesseract
from pdf2image import convert_from_bytes

from odoo import _, fields, models
from odoo.exceptions import UserError

dir_path = os.path.dirname(__file__)


class ImportCSF(models.TransientModel):
    _name = "import.csf"

    file = fields.Binary(required=True, attachment=True)
    file_name = fields.Char()

    def attach_csf(self):
        self.env["ir.attachment"].create(
            {
                "name": self.file_name,
                "datas": self.file,
                "res_model": "res.partner",
                "res_id": self._context.get("active_id"),
            }
        )

    def get_state(self, line):
        state = ""
        split_line = line.split("Nombre de la Entidad Federativa:")[-1].strip()
        if "Entre Calle" in split_line:
            state = split_line.split("Entre Calle")[0]
        else:
            state = line.split("Nombre de la Entidad Federativa:")[-1].strip()
        return state

    def get_zip(self, line):
        zip_code = ""
        split_line = line.split("Codigo Postal:")[-1].strip()
        if "Tipo de" in split_line:
            zip_code = split_line.split("Tipo de")[0].strip()
        else:
            zip_code = line.split("Codigo Postal:")[-1].strip()
        return zip_code

    def upload_csf(self):
        state_obj = self.env["res.country.state"]
        partner_obj = self.env["res.partner"]
        country_obj = self.env["res.country"]
        if self.file_name.split(".")[-1] != "pdf":
            raise UserError(_("Upload file is not in PDF format"))
        file_data = base64.decodebytes(self.file)
        vals = {}
        street = street2 = state = ""
        images = convert_from_bytes(file_data)
        for image in images:
            # Perform OCR on each image
            text = pytesseract.image_to_string(image)

            for line in text.split("\n"):
                if "RFC" in line:
                    vals.update({"vat": line.split("RFC:")[-1].strip()})
                elif "Denominaci6on/Razon Social:" in line:
                    vals.update({"name": line.split(":")[-1].strip()})
                elif "Codigo Postal" in line:
                    vals.update({"zip": self.get_zip(line)})
                elif "Tipo de Vialidad" in line:
                    street += line.split("Tipo de Vialidad:")[-1].strip() + " "
                elif "Nombre de Vialidad" in line:
                    street += line.split("Nombre de Vialidad:")[-1].strip()
                elif "Número Exterior" in line:
                    street += line.split("Número Exterior:")[-1].strip()
                elif "Número Interior" in line:
                    street2 += line.split("Número Interior:")[-1].strip()
                elif "Nombre de la Colonia" in line:
                    street2 += line.split("Nombre de la Colonia:")[-1].strip()
                elif "Nombre del" in line:
                    vals.update({"city": line.split(":")[-1].strip()})
                elif "Nombre de la Entidad Federativa" in line:
                    state = self.get_state(line)

        state_id = state_obj.search([("name", "ilike", state)])
        country_id = country_obj.search([("name", "=", "Mexico")])
        if not state_id:
            state_id = state_obj.search(
                [("code", "ilike", state[0:3]), ("country_id", "=", country_id.id)],
                limit=1,
            )

        vals.update(
            {
                "street": street,
                "street2": street2,
                "state_id": state_id.id,
                "country_id": country_id.id,
            }
        )
        if vals:
            partner_obj.browse(self._context.get("active_id")).write(vals)
            self.attach_csf()
