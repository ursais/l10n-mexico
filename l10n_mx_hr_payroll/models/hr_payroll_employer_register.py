import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


#  Employer Registers
class HrPayrollTableEmployerRegister(models.Model):
    _name = "hr.payroll.employer_register"
    _description = "Payroll Employer Register Table"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Employer Register of IMSS", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", "Company", default=lambda self: self.env.company
    )
    city = fields.Char()
    state_id = fields.Many2one(
        "res.country.state",
        string="Fed. State",
        domain="[('country_id', '=', 'Mexico')]",
    )
    zip = fields.Char(string="ZIP")
    job_risk = fields.Selection(
        [
            ("1", "Class I: Minimum risk"),
            ("2", "Class II: Low risk"),
            ("3", "Class III: Medium risk"),
            ("4", "Class IV: High risk"),
            ("5", "Class V: Maximum risk"),
            ("99", "Not applicable"),
        ],
        default="99",
    )
    job_risk_value = fields.Float(default=0.54355)
    company_zone_l10n_mx = fields.Selection(
        [
            ("z1", "Mexican Zone"),
            ("z2", "Mexico border area"),
        ],
        default="z1",
        string="Company Zone",
        help="Define company zone in Mexico",
    )
