import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrGeneralSalaryIncreaseEmployees(models.TransientModel):
    _name = "hr.general_salary.employees"
    _description = "Generate Increase Salary for all selected employees"

    @api.model
    def default_get(self, fields):
        """Allow support of active_id / active_model instead of jut default_lead_id
        to ease window action definitions, and be backward compatible."""
        return super().default_get(fields)

    def _get_available_contracts_domain(self):
        move_id = self.env.context.get("active_id")
        department_id = (
            self.env["hr.payroll.general_salary_increases"]
            .browse([move_id])
            .department_id.id
        )
        return [
            "&",
            "&",
            ("contract_ids.state", "in", ("open", "close")),
            ("company_id", "=", self.env.company.id),
            ("department_id", "=", department_id),
        ]

    def _get_employees(self):
        active_employee_ids = self.env.context.get("active_employee_ids", False)
        if active_employee_ids:
            return self.env["hr.employee"].browse(active_employee_ids)
        # YTI check dates too
        return self.env["hr.employee"].search(self._get_available_contracts_domain())

    employee_ids = fields.Many2many(
        "hr.employee",
        "hr_salary_employee_group_rel",
        "hr_salary_id",
        "employee_id",
        "Employees",
        default=lambda self: self._get_employees(),
        required=True,
    )
    department_id = fields.Many2one("hr.department", string="Department")

    def compute_sheet(self):
        self.ensure_one()
        if self.env.context.get("active_id"):
            move_id = self.env.context.get("active_id")
            move_employees = self.employee_ids
            move_obj = self.env["hr.payroll.general_salary_increases"].browse([move_id])
            increase_type = move_obj.increase_type
            percent = move_obj.percent
            date_apply = move_obj.date_start

            if increase_type == "percent" and percent <= 0:
                raise ValidationError(_("We Can't calculate with cero percent"))
            amount = move_obj.amount

            move_obj.line_ids.unlink()

            for employee_id in move_employees:
                contract_id = self.env["hr.contract"].search(
                    [("employee_id", "=", employee_id.id), ("state", "=", "open")],
                    limit=1,
                )
                c_wage = contract_id.wage
                c_sdi = contract_id.sdi

                if increase_type == "amount":
                    new_wage = contract_id.wage + amount
                    new_sdi = contract_id.sdi + amount
                else:
                    new_wage = contract_id.wage + (contract_id.wage * (percent / 100))
                    new_sdi = contract_id.sdi + (contract_id.sdi * (percent / 100))

                data_dic = {
                    "line_id": move_obj.id,
                    "employee_id": employee_id.id,
                    "date_apply": date_apply,
                    "contract_id": contract_id.id,
                    "contract_date_start": contract_id.date_start,
                    "c_date": move_obj.current_date,
                    "c_wage": c_wage,
                    "c_sdi": c_sdi,
                    "new_wage": new_wage,
                    "new_sdi": new_sdi,
                    "state": "draft",
                }
                _logger.info(
                    "Current Salary  -->> " + str(c_wage) + "  -  " + str(c_sdi)
                )
                _logger.info("Current Salary  -->> " + str(data_dic))
                self.env["hr.payroll.salary_increases"].create(data_dic)

            return {"type": "ir.actions.act_window_close"}
        else:
            return {"type": "ir.actions.act_window_close"}
