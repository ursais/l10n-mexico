# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


# IMSS Tables
class HrPayrollTableIMSS(models.Model):
    _name = "hr.payroll.imss"
    _description = "Payroll IMSS Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    active = fields.Boolean(default=True)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    enf_mat_cuota_fija = fields.Float(
        string="Fixed fee (%)", default=20.4, digits=(12, 3)
    )
    enf_mat_excedente_p = fields.Float(
        string="Excess of 3 UMA P (%)", default=1.10, digits=(12, 3)
    )
    enf_mat_excedente_e = fields.Float(
        string="Excess of 3 UMA E (%)", default=0.40, digits=(12, 3)
    )

    enf_mat_prestaciones_p = fields.Float(
        string="Cash benefits P (%)", default=0.7, digits=(12, 3)
    )
    enf_mat_prestaciones_e = fields.Float(
        string="cash benefits E (%)", default=0.25, digits=(12, 3)
    )
    enf_mat_gastos_med_p = fields.Float(
        string="Personal medical expenses P (%)", default=1.05, digits=(12, 3)
    )
    enf_mat_gastos_med_e = fields.Float(
        string="Personal medical expenses E (%)", default=0.375, digits=(12, 3)
    )
    inv_vida_p = fields.Float(
        string="Disability and life P (%)", default=1.75, digits=(12, 3)
    )
    inv_vida_e = fields.Float(
        string="Disability and life E (%)", default=0.625, digits=(12, 3)
    )
    cesantia_vejez_p = fields.Float(
        string="Unemployment and old age P (%)", default=3.15, digits=(12, 3)
    )
    cesantia_vejez_e = fields.Float(
        string="Unemployment and old age E (%)", default=1.125, digits=(12, 3)
    )
    retiro_p = fields.Float(string="Retirement (%)", default=2, digits=(12, 3))
    guarderia_p = fields.Float(
        string="Nursery and social benefits (%)", default=1, digits=(12, 3)
    )
