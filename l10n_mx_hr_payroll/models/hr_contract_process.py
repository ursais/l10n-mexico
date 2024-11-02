from odoo import _, api, fields, models


class HrContractProcess(models.Model):
    _name = "hr.contract.process"
    _inherit = ["mail.thread"]
    _description = "Contract process"

    name = fields.Char()
    active = fields.Boolean(default=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    antiquity = fields.Integer()
    department_id = fields.Many2one(
        "hr.department",
        compute="_compute_employee_contract",
        store=True,
        readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        string="Department",
    )
    job_id = fields.Many2one(
        "hr.job",
        compute="_compute_employee_contract",
        store=True,
        readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        string="Job Position",
    )
    date = fields.Date(string="Document date")
    date_start = fields.Date("Start Date", required=True)
    date_end = fields.Date(
        "End Date", help="End date of the contract (if it's a fixed-term contract)."
    )

    contracts_count = fields.Integer(
        compute="_compute_contracts_count", string="Contract Count"
    )
    contract_ids = fields.One2many(
        "hr.contract", "employee_id", string="Employee Contracts"
    )
    contract_id = fields.Many2one(
        "hr.contract",
        string="Current Contract",
        groups="hr.group_hr_user",
        domain="[('company_id', '=', company_id), ('employee_id', '=', id)]",
        help="Current contract of the employee",
        copy=False,
    )
    currency_id = fields.Many2one(
        string="Currency", related="company_id.currency_id", readonly=True
    )
    current_wage = fields.Monetary(compute="_compute_current_wage")
    new_wage = fields.Monetary()
    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        "Working Schedule",
        compute="_compute_employee_contract",
        store=True,
        readonly=False,
        default=lambda self: self.env.company.resource_calendar_id.id,
        copy=False,
        index=True,
        domain="['|', ('company_id', '=', False)," "('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        compute="_compute_employee_contract",
        store=True,
        readonly=False,
        default=lambda self: self.env.company,
        required=True,
    )
    company_country_id = fields.Many2one(
        "res.country",
        string="Company country",
        related="company_id.country_id",
        readonly=True,
    )
    country_code = fields.Char(
        related="company_country_id.code", depends=["company_country_id"], readonly=True
    )
    contract_type_id = fields.Many2one("hr.contract.type")
    renew_type = fields.Selection(
        [
            ("new_date", "New date"),
            ("older_date", "Older Date"),
        ],
        default="older_date",
    )
    process_type = fields.Selection(
        [
            ("renew", "Renew"),
            ("terminate", "Terminate"),
        ],
    )
    reason = fields.Selection(
        [
            ("tc", "Finish contract"),
            ("sv", "Voluntary Separation"),
            ("ae", "Job Abandonment"),
            ("def", "Death"),
            ("cla", "Clause"),
            ("oth", "Others"),
            ("aus", "Absenteeism"),
            ("rc", "Termination of contract"),
            ("jub", "Retirement"),
            ("pen", "Pension"),
        ]
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_process", "In Process"),
            ("approved", "Approved"),
            ("cancel", "Canceled"),
        ],
        default="draft",
    )

    #   Button Functions

    def approved_process(self):
        for process in self:
            if process.name == _("New"):
                process.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.process"
                ) or _("New")
            process.state = "approved"
            if process.process_type == "terminate":
                process.contract_id.date_end = process.date_end
                process.contract_id.state = "cancel"
            else:
                process.contract_id.date_end = process.date_end
                process.contract_id.state = "cancel"
                new_contract_data = {
                    "name": process.contract_id.name,
                    "employee_id": process.employee_id.id,
                    "date_start": process.date_start,
                    "resource_calendar_id": process.contract_id.resource_calendar_id.id,
                    "work_entry_source": process.contract_id.work_entry_source,
                    "department_id": process.contract_id.department_id.id,
                    "journal_type": process.contract_id.journal_type,
                    "job_id": process.contract_id.job_id.id,
                    "hr_responsible_id": process.contract_id.hr_responsible_id.id,
                    "structure_type_id": process.contract_id.structure_type_id.id,
                    "salary_type": process.contract_id.salary_type,
                    "allowance_catalog": process.contract_id.allowance_catalog.id,
                    "contract_type": process.contract_id.contract_type,
                    "wage": process.new_wage,
                    "state": "open",
                }
                contract_id = self.env["hr.contract"].sudo().create(new_contract_data)
                contract_id.update_sdi()
            self.message_post(
                body=_(
                    "Payroll Process Contract  with folio <b>%(process.name)s</b>\
                        has been changed to Approve status"
                )
            )
            return True

    def cancel_process(self):
        for process in self:
            if process.name == _("New"):
                process.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.process"
                ) or _("New")
            process.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Process Contract  with folio <b>%(process.name)s</b>\
                        has been changed to Approve status",
                )
            )
            return True

    def draft_process(self):
        for process in self:
            if process.name == _("New"):
                process.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.process"
                ) or _("New")
            process.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Process Contract  with folio <b>%(process.name)s</b>\
                        has been changed to Draft status",
                )
            )
            return True

    @api.depends("contract_id")
    def _compute_current_wage(self):
        for process in self:
            if process.contract_id:
                process.current_wage = process.contract_id.wage
            else:
                process.current_wage = 0

    @api.depends("employee_id")
    def _compute_employee_contract(self):
        for contract in self.filtered("employee_id"):
            contract.job_id = contract.employee_id.job_id
            contract.department_id = contract.employee_id.department_id
            contract.resource_calendar_id = contract.employee_id.resource_calendar_id
            contract.company_id = contract.employee_id.company_id

    def _current_contract(self, employee_id):
        contract_id = employee_id.contract_ids.filtered(lambda c: (c.state in ["open"]))
        return contract_id

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id:
            self.date = fields.Date.today()
            self.date_end = fields.Date.today()
            self.antiquity = self._current_contract(self.employee_id).antiquity
            self.date_start = self._current_contract(self.employee_id).date_start
            self.contract_id = self._current_contract(self.employee_id).id
            self.job_id = self.employee_id.job_id.id or False
            self.department_id = self.employee_id.department_id.id or False
            self.new_wage = self.contract_id.wage + 1
            if self.process_type == "renew":
                self.name = _("Renew contract " + "[ " + self.employee_id.name + " ]")
            else:
                self.name = _(
                    "Terminate contract " + "[ " + self.employee_id.name + " ]"
                )
