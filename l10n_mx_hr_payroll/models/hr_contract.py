from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    antiquity = fields.Integer(
        compute="_compute_antiquity",
    )
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
        "hr.payroll.period",
        string="Pay period",
    )
    salary_type = fields.Selection(
        [("01", "Fixed"), ("02", "Mixte"), ("03", "Variable")],
        help="Salary Type",
    )
    restday_ids = fields.Many2many(
        "hr.contract.restday",
        "contract_rest_days_rel",
        "contract_id",
        "day_id",
        groups="hr.group_hr_user",
        string="Rest days",
    )
    allowance_catalog = fields.Many2one("hr.payroll.pc", string="Allowance Table")
    sdi = fields.Float(string="SDI", help="Salario diario integrado")
    sbc = fields.Float(string="SBC", help="Salario base de cotización")
    salaries_history_count = fields.Integer(
        compute="_compute_salaries_history_count", string="Salary history count"
    )
    salary_history_ids = fields.Many2many(
        "hr.contract.salary_history",
        compute="_compute_salaries_history_count",
        string="Salary history IDs",
        copy=False,
    )

    @api.model
    def _update_sdi_and_sbc(self):
        for contract in self.search([]):
            contract.update_sdi()

    @api.depends("date_start", "first_contract_date")
    def _compute_antiquity(self):
        for contract in self:
            if contract.first_contract_date:
                days = (fields.Date.today() - contract.first_contract_date).days
                contract.antiquity = int(days / 365)
            else:
                contract.antiquity = 0

    @api.onchange("wage", "allowance_catalog")
    def update_sdi(self):
        for contract in self:
            antiquity = contract.antiquity
            line_pc = contract.env["hr.payroll.pc.line"].search(
                [
                    ("antiquity", ">", antiquity),
                ],
                limit=1,
            )
            if line_pc:
                contract.sdi = contract.wage * (
                    1
                    + round((line_pc.bonus / 365), 4)
                    + round(((line_pc.holidays * (line_pc.pvp / 100)) / 365), 4)
                )
                contract.sbc = contract.wage * (
                    1
                    + round((line_pc.bonus / 365), 4)
                    + round(((line_pc.holidays * (line_pc.pvp / 100)) / 365), 4)
                )

    def _compute_salaries_history_count(self):
        history_salary_obj = self.env["hr.contract.salary_history"]
        for contract in self:
            salaries_history = history_salary_obj.search(
                [("contract_id", "=", contract.id)]
            )
            contract.salary_history_ids = salaries_history
            contract.salaries_history_count = len(salaries_history)

    def action_view_salary_histories(self, salaries_history=False):
        if not salaries_history:
            self.sudo()._read(["salary_history_ids"])
            salaries_history = self.salary_history_ids
        result = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_mx_hr_payroll.hr_salaries_history_action"
        )
        if len(salaries_history) > 1:
            result["domain"] = [("id", "in", salaries_history.ids)]
        elif len(salaries_history) == 1:
            res = self.env.ref("hr.contract.salary_history", False)
            form_view = [(res and res.id or False, "form")]
            if "views" in result:
                result["views"] = form_view + [
                    (state, view) for state, view in result["views"] if view != "form"
                ]
            else:
                result["views"] = form_view
            result["res_id"] = salaries_history.id
        else:
            result = {"type": "ir.actions.act_window_close"}
        return result
