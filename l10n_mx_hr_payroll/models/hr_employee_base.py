from odoo import fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    firstname = fields.Char()
    lastname = fields.Char()
    second_lastname = fields.Char()
    state_of_birth = fields.Many2one("res.country.state")
    employee_number = fields.Char()
    umf = fields.Integer(help="Family Medical Unit")
    syndicated = fields.Boolean()
    l10n_mx_hr_payroll_fiscal_regime = fields.Selection(
        [
            (
                "02",
                "Salaries (Includes income specified in section I of article "
                "94 of the Income Tax Law)",
            ),
            ("03", "Retired"),
            ("04", "Pensioners"),
            ("05", "Assimilated Members Cooperative Societies Production"),
            ("06", "Assimilated Members Societies Civil Associations"),
            ("07", "Assimilated Members Councils"),
            ("08", "Assimilated Commission Agents"),
            ("09", "Assimilated Fees"),
            ("10", "Assimilated Actions"),
            ("11", "Assimilated Others"),
            ("12", "Retired or Pensioners"),
            ("13", "Compensation or Separation"),
            ("99", "Other Regime"),
        ],
        help="" "Employee Regime.",
    )
    employer_register = fields.Many2one("hr.payroll.employer_register")

    _sql_constraints = [
        (
            "unique_employee_number",
            "UNIQUE(employee_number)",
            "Only one employee number per company",
        ),
    ]
