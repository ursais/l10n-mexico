import logging
from collections import defaultdict
from datetime import date, datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class HrPayslipEmployees(models.TransientModel):
    _name = "hr.payslip.employees"
    _description = "Generate payslips for all selected employees"

    def _get_available_contracts_domain(self):
        return [
            ("contract_ids.state", "in", ("open", "close")),
            (
                "contract_ids.structure_type_id.id",
                "=",
                self._get_structure().type_id.id,
            ),
            ("company_id", "=", self.env.company.id),
        ]

    def _get_structure(self):
        if self.env.context.get("active_ids", []):
            payslip_run_id = self.env.context.get("active_ids", [])[0]
        else:
            payslip_run_id = []

        return self.env["hr.payslip.run"].browse(payslip_run_id).structure_id

    def _get_employees(self):
        active_employee_ids = self.env.context.get("active_employee_ids", False)
        if active_employee_ids:
            return self.env["hr.employee"].browse(active_employee_ids)
        return self.env["hr.employee"].search(self._get_available_contracts_domain())

    employee_ids = fields.Many2many(
        "hr.employee",
        "hr_employee_group_rel",
        "payslip_id",
        "employee_id",
        "Employees",
        default=lambda self: self._get_employees(),
        required=True,
    )
    structure_id = fields.Many2one(
        "hr.payroll.structure",
        string="Salary Structure",
        default=lambda self: self._get_structure(),
        required=True,
    )
    department_id = fields.Many2one("hr.department")

    @api.depends("department_id")
    def _compute_employee_ids(self):
        for wizard in self:
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND(
                    [domain, [("department_id", "child_of", self.department_id.id)]]
                )
            wizard.employee_ids = self.env["hr.employee"].search(domain)

    def _check_undefined_slots(self, work_entries, payslip_run):
        """
        Check if a time slot in the contract's calendar is not covered by a work entry
        """
        work_entries_by_contract = defaultdict(lambda: self.env["hr.work.entry"])
        for work_entry in work_entries:
            work_entries_by_contract[work_entry.contract_id] |= work_entry

        for contract, work_entries in work_entries_by_contract.items():
            calendar_start = pytz.utc.localize(
                datetime.combine(
                    max(contract.date_start, payslip_run.date_start), time.min
                )
            )
            calendar_end = pytz.utc.localize(
                datetime.combine(
                    min(contract.date_end or date.max, payslip_run.date_end), time.max
                )
            )
            outside = (
                contract.resource_calendar_id._attendance_intervals_batch(
                    calendar_start, calendar_end
                )[False]
                - work_entries._to_intervals()
            )
            if outside:
                time_intervals_str = "\n - ".join(
                    ["", *["%s -> %s" % (s[0], s[1]) for s in outside._items]]
                )
                raise UserError(
                    _(
                        "Some part of %(name)s's calendar is not covered by "
                        "any "
                        "work entry. "
                        "Please complete the schedule. "
                        "Time intervals to look for: %(interval)s"
                    )
                    % {
                        "name": contract.employee_id.name,
                        "interval": time_intervals_str,
                    }
                )

    def _filter_contracts(self, contracts):
        # Could be overriden to avoid having 2 'end of the year bonus' payslips, etc.
        return contracts

    def compute_sheet(self):
        self.ensure_one()
        if not self.env.context.get("active_id"):
            from_date = fields.Date.to_date(self.env.context.get("default_date_start"))
            end_date = fields.Date.to_date(self.env.context.get("default_date_end"))
            payslip_run = self.env["hr.payslip.run"].create(
                {
                    "name": from_date.strftime("%B %Y"),
                    "date_start": from_date,
                    "date_end": end_date,
                }
            )
        else:
            payslip_run = self.env["hr.payslip.run"].browse(
                self.env.context.get("active_id")
            )

        employees = self.with_context(active_test=False).employee_ids
        if not employees:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        # Prevent a payslip_run from having multiple payslips for the same employee
        employees -= payslip_run.slip_ids.employee_id
        success_result = {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip.run",
            "views": [[False, "form"]],
            "res_id": payslip_run.id,
        }
        if not employees:
            return success_result

        payslips = self.env["hr.payslip"]
        Payslip = self.env["hr.payslip"]

        contracts = employees._get_contracts(
            payslip_run.date_start, payslip_run.date_end, states=["open", "close"]
        ).filtered(lambda c: c.active)
        _logger.info(
            "Payslips Dates  --->>>  "
            + str(payslip_run.date_start)
            + " - "
            + str(payslip_run.date_end)
        )
        # contracts._generate_work_entries(payslip_run.date_start, payslip_run.date_end)
        contracts._generate_work_entries(datetime(2023, 6, 1), datetime(2023, 7, 31))
        work_entries = self.env["hr.work.entry"].search(
            [
                ("date_start", "<=", payslip_run.date_end),
                ("date_stop", ">=", payslip_run.date_start),
                ("employee_id", "in", employees.ids),
            ]
        )
        self._check_undefined_slots(work_entries, payslip_run)

        if self.structure_id.type_id.default_struct_id == self.structure_id:
            work_entries = work_entries.filtered(
                lambda work_entry: work_entry.state != "validated"
            )
            if work_entries._check_if_error():
                work_entries_by_contract = defaultdict(
                    lambda: self.env["hr.work.entry"]
                )

                for work_entry in work_entries.filtered(
                    lambda w: w.state == "conflict"
                ):
                    work_entries_by_contract[work_entry.contract_id] |= work_entry

                for _contract, work_entries in work_entries_by_contract.items():
                    conflicts = work_entries._to_intervals()
                    time_intervals_str = "\n - ".join(
                        ["", *["%s -> %s" % (s[0], s[1]) for s in conflicts._items]]
                    )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Some work entries could not be validated."),
                        "message": _(
                            "Time intervals to look for:%s", time_intervals_str
                        ),
                        "sticky": False,
                    },
                }

        default_values = Payslip.default_get(Payslip.fields_get())
        payslips_vals = []
        for contract in self._filter_contracts(contracts):
            values = dict(
                default_values,
                **{
                    "name": _("New Payslip"),
                    "employee_id": contract.employee_id.id,
                    "payslip_run_id": payslip_run.id,
                    "date_from": payslip_run.date_start,
                    "date_to": payslip_run.date_end,
                    "payment_day": payslip_run.payment_day,
                    "contract_id": contract.id,
                    "struct_id": self.structure_id.id
                    or contract.structure_type_id.default_struct_id.id,
                },
            )
            payslips_vals.append(values)
        payslips = Payslip.with_context(tracking_disable=True).create(payslips_vals)
        payslips._compute_name()
        payslips.compute_sheet()
        payslip_run.state = "verify"

        return success_result


class HrMovementEmployees(models.TransientModel):
    _name = "hr.movement.employees"
    _description = "Generate movement for all selected employees"

    @api.model
    def default_get(self, fields):
        return super().default_get(fields)

    def _get_available_contracts_domain(self):
        return [
            ("contract_ids.state", "in", ("open", "close")),
            ("company_id", "=", self.env.company.id),
        ]

    def _get_employees(self):
        active_employee_ids = self.env.context.get("active_employee_ids", False)
        if active_employee_ids:
            return self.env["hr.employee"].browse(active_employee_ids)
        return self.env["hr.employee"].search(self._get_available_contracts_domain())

    employee_ids = fields.Many2many(
        "hr.employee",
        "hr_move_employee_group_rel",
        "hr_movement_id",
        "employee_id",
        "Employees",
        default=lambda self: self._get_employees(),
        required=True,
    )

    department_id = fields.Many2one("hr.department")

    def compute_sheet(self):
        self.ensure_one()
        if not self.env.context.get("active_id"):
            # structure_id =
            from_date = fields.Date.to_date(self.env.context.get("default_date_start"))
            end_date = fields.Date.to_date(self.env.context.get("default_date_end"))
            movement_employee = self.env["hr.movement.employees"].create(
                {
                    "name": from_date.strftime("%B %Y"),
                    "date_start": from_date,
                    "date_end": end_date,
                }
            )
        else:
            movement_employee = self.env["hr.payroll.movement"].browse(
                self.env.context.get("active_id")
            )

        default_values = {}
        employee_values = [
            dict(
                default_values,
                **{
                    "name": "Movement",
                    "employee_id": employee.id,
                    "date_start": movement_employee.date_start,
                    "date_end": movement_employee.date_end,
                    "payslip_input_id": movement_employee.payslip_input_id.id,
                    "multi_form": True,
                    "amount": movement_employee.amount,
                    "line_id": movement_employee.id,
                },
            )
            for employee in self.employee_ids
        ]
        self.env["hr.payroll.movement.line"].with_context(tracking_disable=True).create(
            employee_values
        )
        return {"type": "ir.actions.act_window_close"}
