# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models


# Payroll Loans
class HrPayrollSettlements(models.Model):
    _name = "hr.payroll.settlements"
    _description = "Payroll Settlements"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="_New")
    employee_id = fields.Many2one("hr.employee")
    contract_id = fields.Many2one(
        "hr.contract", compute="_compute_contract_id", store=True
    )
    department_id = fields.Many2one(
        "hr.department", related="contract_id.department_id", readonly=True
    )
    date_start = fields.Date()
    date_end = fields.Date()
    antiquity = fields.Integer(related="contract_id.antiquity", readonly=True)
    reason_for_dismissal = fields.Selection(
        [
            ("expired_contract", "Contract Expiration"),
            ("voluntary_separation", "Voluntary Separation"),
            ("job_abandonment", "Job Abandonment"),
            ("death", "Death"),
            ("closing", "Closing"),
            ("others", "Others"),
            ("absenteeism", "Absenteeism"),
            ("termination_of_contract_just", "Justified termination of contract"),
            ("termination_of_contract_unjust", "Unjustified termination of contract"),
            ("rescission", "Rescission"),
        ],
    )
    payslip_run_id = fields.Many2one("hr.payslip.run")
    payslip_id = fields.Many2one("hr.payslip")

    payroll_type_id = fields.Many2one("hr.payroll.period.type", string="Payroll Type")
    payroll_period_id = fields.Many2one("hr.payroll.period", string="Payroll Period")
    payroll_period_line_id = fields.Many2one(
        "hr.payroll.period.line", string="Payroll Period line"
    )
    cdate_start = fields.Date()
    cdate_end = fields.Date(required=True)
    payment_day = fields.Date()
    currency_id = fields.Many2one(
        string="Currency", related="company_id.currency_id", readonly=True
    )
    wage = fields.Monetary(compute="_compute_current_wage")
    structure_id = fields.Many2one("hr.payroll.structure", string="Payroll Structure")
    settlement_type = fields.Selection(
        [
            ("settlement", "Settlement"),
            ("liquidation", "Liquidation"),
        ],
        compute="_compute_settlement_type",
    )
    notes = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    @api.depends("employee_id")
    def _compute_contract_id(self):
        for record in self:
            record.contract_id = (
                record.employee_id and record.employee_id.contract_id.id or False
            )

    @api.depends("reason_for_dismissal")
    def _compute_settlement_type(self):
        for record in self:
            if not record.reason_for_dismissal:
                record.settlement_type = False
            elif (
                record.reason_for_dismissal == "expired_contract"
                or record.reason_for_dismissal == "voluntary_separation"
                or record.reason_for_dismissal == "job_abandonment"
                or record.reason_for_dismissal == "death"
                or record.reason_for_dismissal == "others"
                or record.reason_for_dismissal == "absenteeism"
                or record.reason_for_dismissal == "termination_of_contract_just"
            ):
                record.settlement_type = "settlement"
            elif (
                record.reason_for_dismissal == "closing"
                or record.reason_for_dismissal == "termination_of_contract_unjust"
                or record.reason_for_dismissal == "rescission"
            ):
                record.settlement_type = "liquidation"

    @api.depends("contract_id")
    def _compute_current_wage(self):
        for settlement in self:
            if settlement.contract_id:
                settlement.wage = settlement.contract_id.wage
            else:
                settlement.wage = 0

    def action_view_payslip(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "=", self.payslip_id.id]],
            "name": "Payslips",
        }

    @api.onchange("contract_id")
    def _onchange_contract(self):
        if self.contract_id:
            self.cdate_start = self.contract_id.date_start
            return
        return

    @api.onchange("payroll_type_id", "payroll_period_id", "payroll_period_line_id")
    def _onchange_employee(self):
        if (
            (self.payroll_type_id)
            and (self.payroll_period_id)
            and (self.payroll_period_line_id)
        ):
            self.date_start = self.payroll_period_line_id.date_start
            self.date_end = self.payroll_period_line_id.date_end
            self.payment_day = self.payroll_period_line_id.date_pay
            self.structure_id = self.payroll_period_id.structure_id
            self.name = "Payroll [ " + self.payroll_period_line_id.name + " ]"
            return
        return

    def approved_settlement(self):
        for settlement in self:
            if settlement.name == _("_New"):
                settlement.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.settlement"
                ) or _("New")
            status = settlement.state
            settlement.state = "approved"
            payslip = self.env["hr.payslip"]
            settlement.payslip_id = payslip.create(
                {
                    "name": "Settlement for " + str(settlement.employee_id),
                    "state": "draft",
                    "employee_id": settlement.employee_id.id,
                    "date_from": settlement.cdate_start,
                    "date_to": settlement.cdate_end,
                    "payment_day": settlement.payment_day,
                    "contract_id": settlement.contract_id.id,
                }
            )
            if settlement.settlement_type == "settlement":
                if (
                    settlement.contract_id.structure_type_id.id
                    == self.env.ref(
                        "l10n_mx_hr_payroll.structure_type_employee_weekly_mx"
                    ).id
                ):
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_weekly_settlement"
                            ).id,
                        }
                    )
                elif (
                    settlement.contract_id.structure_type_id.id
                    == self.env.ref(
                        "l10n_mx_hr_payroll.structure_mx_employee_biweekly"
                    ).id
                ):
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_biweekly_settlement"
                            ).id,
                        }
                    )
                else:
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_special_settlement"
                            ).id,
                        }
                    )
            elif settlement.settlement_type == "liquidation":
                if (
                    settlement.contract_id.structure_type_id.id
                    == self.env.ref(
                        "l10n_mx_hr_payroll.structure_type_employee_weekly_mx"
                    ).id
                ):
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_weekly_liquidation"
                            ).id,
                        }
                    )
                elif (
                    settlement.contract_id.structure_type_id.id
                    == self.env.ref(
                        "l10n_mx_hr_payroll.structure_mx_employee_biweekly"
                    ).id
                ):
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_biweekly_liquidation"
                            ).id,
                        }
                    )
                else:
                    settlement.payslip_id.write(
                        {
                            "struct_id": self.env.ref(
                                "l10n_mx_hr_payroll.structure_mx_special_liquidation"
                            ).id,
                        }
                    )
            self.message_post(
                body=_(
                    "Payroll settlement has been changed <b>%s</b> to Approve status",
                    status,
                )
            )
            return True

    def done_settlement(self):
        for settlement in self:
            status = settlement.state
            settlement.state = "done"
            self.message_post(
                body=_(
                    "Payroll settlement has been changed <b>%s</b> to Done status",
                    status,
                )
            )
            return True

    def draft_settlement(self):
        for settlement in self:
            status = settlement.state
            settlement.state = "draft"
            self.message_post(
                body=_(
                    "Payroll settlement has been changed <b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def cancel_settlement(self):
        for settlement in self:
            status = settlement.state
            settlement.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll settlement has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
