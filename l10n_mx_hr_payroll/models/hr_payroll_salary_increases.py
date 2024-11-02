import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Payroll General Salary Increases


class HrPayrollGeneralSalaryIncreases(models.Model):
    _name = "hr.payroll.general_salary_increases"
    _description = "Payroll General Salary Increases"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Folio", default="New")
    current_date = fields.Date(default=fields.Date.today)
    date_start = fields.Date(string="Date apply")
    movs_count = fields.Integer(compute="_compute_movs_count")
    amount = fields.Monetary(help="")
    percent = fields.Float(help="")
    department_id = fields.Many2one("hr.department", string="Department", required=True)
    increase_type = fields.Selection(
        [
            ("percent", "Percent"),
            ("amount", "Amount"),
        ]
    )
    notes = fields.Text()
    currency_id = fields.Many2one(
        string="Currency", related="company_id.currency_id", readonly=True
    )
    line_ids = fields.One2many(
        "hr.payroll.salary_increases",
        "line_id",
        string="Lines",
        states={"cancel": [("readonly", True)], "done": [("readonly", True)]},
        copy=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("applied", "Applied"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    def _compute_movs_count(self):
        for movs in self:
            movs.movs_count = len(movs.line_ids)

    def action_open_payroll_wage_increase(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payroll.salary_increases",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.line_ids.ids]],
            "name": "Payroll Movements of Salary Increase",
        }

    def approved_salary_increase(self):
        for salary_increase in self:
            if salary_increase.name == _("New"):
                salary_increase.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.general_salary_increases"
                ) or _("New")
            for line in salary_increase.line_ids:
                line.approved_salary_increase()
            salary_increase.state = "approved"
            status = salary_increase.state
            self.message_post(
                body=_(
                    "Payroll General Salary Increase has been changed"
                    "<b>%s</b> to Cancel status",
                    status,
                )
            )
        return True

    def cancel_salary_increase(self):
        for salary_increase in self:
            salary_increase.state = "cancel"
            status = salary_increase.state
            self.message_post(
                body=_(
                    "Payroll General Salary Increase has been changed "
                    "<b>%s</b> to Cancel status",
                    status,
                )
            )
            return True

    def draft_salary_increase(self):
        for salary_increase in self:
            status = salary_increase.state
            salary_increase.state = "draft"
            self.message_post(
                body=_(
                    "Payroll General Salary Increase has been changed "
                    "<b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def execute_cron_compute_general_salary_increase(self):
        for salary_increase in self.search([("state", "=", "approved")]):
            salary_increase.state = "applied"


# Payroll Salary Increases
class HrPayrollSalaryIncreases(models.Model):
    _name = "hr.payroll.salary_increases"
    _description = "Payroll Salary Increases"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Folio", default="New")
    date_apply = fields.Date(string="Date apply")
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    contract_id = fields.Many2one("hr.contract", string="Contract")
    line_id = fields.Many2one(
        "hr.payroll.general_salary_increases",
        string="Order Reference",
        index=True,
        required=False,
        ondelete="cascade",
    )
    salary_history_id = fields.Many2one(
        "hr.contract.salary_history", string="Salary History"
    )
    contract_date_start = fields.Date(
        string="Date Start", related="contract_id.date_start"
    )
    contract_date_end = fields.Date(string="Date end")
    date_start = fields.Date(string="Date apply")
    c_date = fields.Date(string="Current Date", default=fields.Date.today)
    c_wage = fields.Monetary("Current Wage", required=False, help="", readonly=True)
    c_sdi = fields.Monetary("Current SDI", help="", readonly=True)
    new_date = fields.Date(string="New date", default=fields.Date.today)
    new_wage = fields.Monetary(tracking=True, help="")
    new_sdi = fields.Monetary("New SDI", help="")
    currency_id = fields.Many2one(
        string="Currency", related="company_id.currency_id", readonly=True
    )
    salary_type = fields.Selection(
        [("01", "Fijo"), ("02", "Mixto"), ("03", "Variable")],
    )
    allowance_catalog = fields.Many2one("hr.payroll.pc", string="Allowance Table")
    increase_type = fields.Selection(
        [
            ("percent", "Percent"),
            ("amount", "Amount"),
        ],
    )
    notes = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("applied", "Applied"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    @api.model
    def execute_cron_compute_salary_increase(self):
        move_ids = self.env["hr.contract.salary_history"].search(
            [("state", "=", "approved")]
        )

        _logger.info(
            "###  execute_cron_compute_salary_increase  ###  ( "
            + str(len(move_ids))
            + " )"
        )
        for move_id in move_ids:
            if move_id.date_applied == fields.Date.today():
                _logger.info(
                    "###  execute_cron_compute_salary_increase  ###" + str(move_id.id)
                )
                move_id.name = "History of contract Applied - %s" % str(
                    fields.Date.today()
                )
                move_id.contract_id.wage = move_id.wage
                move_id.contract_id.sdi = move_id.sdi
                move_id.salary_increase_id.state = "applied"
                move_id.state = "applied"

        self.line_id.state = "applied"
        self.env[
            "hr.payroll.general_salary_increases"
        ].execute_cron_compute_general_salary_increase()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "new_date" in vals:
                if not vals.get("new_date"):
                    raise UserError(
                        _("You need to set a new date to apply the new wage")
                    )
            if "company_id" in vals:
                self = self.with_company(vals["company_id"])
            if "employee_id" in vals:
                employee = self.env["hr.employee"].browse([vals.get("employee_id")])
                contract_obj = self.env["hr.contract"].search(
                    [("employee_id", "=", employee.id), ("state", "=", "open")], limit=1
                )

                vals["contract_id"] = contract_obj.id
                vals["salary_type"] = (
                    self.env["hr.contract"]
                    .search(
                        [("employee_id", "=", employee.id), ("state", "=", "open")],
                        limit=1,
                    )
                    .salary_type
                    or False
                )
                vals["c_wage"] = (
                    self.env["hr.contract"]
                    .search(
                        [("employee_id", "=", employee.id), ("state", "=", "open")],
                        limit=1,
                    )
                    .wage
                )

                vals["c_sdi"] = (
                    self.env["hr.contract"]
                    .search(
                        [("employee_id", "=", employee.id), ("state", "=", "open")],
                        limit=1,
                    )
                    .sdi
                )

                antiquity = contract_obj.antiquity
                line_pc = self.env["hr.payroll.pc.line"].search(
                    [
                        ("antiquity", ">", antiquity),
                    ],
                    limit=1,
                )

        result = super().create(vals)
        return result

    def write(self, vals):
        if vals.get("amount"):
            self.message_post(
                body=_(
                    "Payroll Salary Increase has been modify amount with $ <b>%.4f</b>",
                    vals.get("amount"),
                )
            )
        write_result = super().write(vals)
        return write_result

    def unlink(self):
        for move in self:
            if move.state != "draft":
                raise UserError(_("You can not delete this Salary increase Movement."))
        return super().unlink()

    @api.onchange("new_wage")
    def update_sdi(self):
        for move in self:
            antiquity = move.contract_id.antiquity
            line_pc = move.env["hr.payroll.pc.line"].search(
                [
                    ("antiquity", ">", antiquity),
                ],
                limit=1,
            )
            if line_pc:
                move.new_sdi = move.new_wage * (
                    1
                    + round((line_pc.bonus / 365), 4)
                    + round(((line_pc.holidays * (line_pc.pvp / 100)) / 365), 4)
                )

    def approved_salary_increase(self):
        for move in self:
            if move.name == _("New"):
                move.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.salary_increases"
                ) or _("New")
            move.contract_id.update_sdi()
            salary_history_dict = {
                "salary_increase_id": move.id,
                "employee_id": move.employee_id.id,
                "contract_id": move.contract_id.id,
                "salary_type": move.salary_type,
                "older_wage": move.c_wage,
                "older_sdi": move.c_sdi,
                "date": move.new_date,
                "date_applied": move.date_apply,
                "wage": move.new_wage,
                "sdi": move.new_sdi,
                "contract_type": move.contract_id.contract_type,
                "journal_type": move.contract_id.journal_type,
                "period_cfdi": move.contract_id.period_cfdi.id,
                "state": "approved",
            }
            move.salary_history_id = (
                self.env["hr.contract.salary_history"].create(salary_history_dict).id
            )
            # self.update_salary_contract()
            if move.name == "New":
                move.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.salary_increases"
                ) or _("New")
            status = move.state
            move.state = "approved"
            self.message_post(
                body=_(
                    "Payroll Salary Increase has been changed <b>%s</b> to Approve status",
                    status,
                )
            )
        return True

    def _update_salary_contract(self):
        pass
        to_process = self.env["hr.payroll.salary_increases"].search(
            [("state", "=", "approved")]
        )
        for move in to_process:
            user_tz = move.employee_id.tz
            if (
                move.salary_history_id.date <= fields.Date.today(pytz.timezone(user_tz))
                and move.salary_history_id.state == "to_process"
                and move.state == "approved"
            ):
                move.contract_id.wage = move.new_wage
                move.contract_id.update_sdi()
                move.salary_history_id.state = "applied"
                move.state = "done"
                _logger.info(_("Update Salary for employees "))

    def done_salary_increase(self):
        for salary_increase in self:
            status = salary_increase.state
            salary_increase.state = "done"
            self.message_post(
                body=_(
                    "Payroll Salary Increase has been changed <b>%s</b> to Done status",
                    status,
                )
            )
            return True

    def draft_salary_increase(self):
        for salary_increase in self:
            status = salary_increase.state
            salary_increase.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Salary Increase has been changed <b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def cancel_salary_increase(self):
        for salary_increase in self:
            history_id = salary_increase.env["hr.contract.salary_history"].search(
                [("salary_increase_id", "=", salary_increase.id)], limit=1
            )
            history_id.state = "cancel"
            status = salary_increase.state
            salary_increase.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Salary Increase has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True

    @api.onchange("employee_id")
    def onchange_employee(self):
        for move in self:
            if move.employee_id:
                move.contract_id = self.env["hr.contract"].search(
                    [("employee_id", "=", move.employee_id.id), ("state", "=", "open")],
                    limit=1,
                )
                move.c_wage = (
                    self.env["hr.contract"]
                    .search(
                        [
                            ("employee_id", "=", move.employee_id.id),
                            ("state", "=", "open"),
                        ],
                        limit=1,
                    )
                    .wage
                    or 0.00
                )
                move.c_sdi = (
                    self.env["hr.contract"]
                    .search(
                        [
                            ("employee_id", "=", move.employee_id.id),
                            ("state", "=", "open"),
                        ],
                        limit=1,
                    )
                    .sdi
                    or 0.00
                )
                move.new_wage = (
                    self.env["hr.contract"]
                    .search(
                        [
                            ("employee_id", "=", move.employee_id.id),
                            ("state", "=", "open"),
                        ],
                        limit=1,
                    )
                    .wage
                    or 0.00
                )
                move.new_sdi = (
                    self.env["hr.contract"]
                    .search(
                        [
                            ("employee_id", "=", move.employee_id.id),
                            ("state", "=", "open"),
                        ],
                        limit=1,
                    )
                    .sdi
                    or 0.00
                )
                move.salary_type = move.contract_id.salary_type
