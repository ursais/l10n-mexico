from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    curp = fields.Char(string="CURP", help="CURP")
