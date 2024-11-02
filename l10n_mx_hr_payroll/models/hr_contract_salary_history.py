from odoo import api, fields, models


class HrContractSalaryHistory(models.Model):
    _name = "hr.contract.salary_history"
    _description = "Payroll Contract Salary History"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    salary_increase_id = fields.Many2one(
        "hr.payroll.salary_increases", "Salary Increase"
    )
    employee_id = fields.Many2one("hr.employee", "Employee")
    contract_id = fields.Many2one("hr.contract", "Contract")
    salary_type = fields.Selection(
        [("01", "Fixed"), ("02", "Mixte"), ("03", "Variable")],
        help="Salary Type",
    )
    date = fields.Date()
    date_applied = fields.Date(string="Date to apply")
    contract_type = fields.Selection(
        [
            ("01", "Indefinite-term employment contract"),
            ("02", "Employment contract for specific work"),
            ("03", "Employment contract for a specific period"),
            ("04", "Seasonal employment contract"),
            ("05", "Probationary employment contract"),
            ("06", "Employment contract with initial training"),
            ("07", "Hiring modality for payment of hours worked"),
            ("08", "Modality of work by labor commission"),
            ("09", "Hiring modalities where there is no employment relationship"),
            ("10", "Retirement, pension, withdrawal"),
            ("99", "Other contract"),
        ],
        help="Contract Type",
    )
    older_wage = fields.Float()
    older_sdi = fields.Float(string="Older SDI")
    wage = fields.Float()
    sdi = fields.Float(string="SDI")
    journal_type = fields.Selection(
        [
            ("00", "Normal"),
            ("01", "1 day"),
            ("02", "2 days"),
            ("03", "3 days"),
            ("04", "4 days"),
            ("05", "5 days"),
            ("06", "Reduced day"),
        ],
        help="",
    )
    period_cfdi = fields.Many2one(
        "hr.payroll.period", string="Periodo de pago", help="Periodo de Pago"
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_process", "To process"),
            ("approved", "Approved"),
            ("applied", "Applied"),
            ("cancel", "Cancel"),
        ],
        help="",
    )
    notes = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        return result
