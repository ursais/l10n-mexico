import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from odoo.tools.misc import format_date

from odoo.addons.hr_payroll.models.browsable_object import (
    BrowsableObject,
    InputLine,
    Payslips,
    ResultRules,
    WorkedDays,
)

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    country_code = fields.Char(related="company_id.country_id.code", readonly=True)
    payment_day = fields.Date()
    hide_rule = fields.Boolean(tracking=True)
    extratime_count = fields.Integer(compute="_compute_extratime_count")
    extratime_ids = fields.Many2many(
        "hr.payroll.extratime.line",
        compute="_compute_extratime_count",
        copy=False,
    )
    payslip_date = fields.Date(
        readonly=True,
        index=True,
        copy=False,
        states={"draft": [("readonly", False)]},
    )
    allowance_total = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    deduction_total = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    other_payments = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    amount_subtotal = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    discount = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    retentions = fields.Monetary(
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    amount_total = fields.Monetary(
        string="Total",
        store=False,
        readonly=True,
        compute="_compute_amount",
        inverse="_inverse_amount_total",
    )
    amount_total_signed = fields.Monetary(
        string="Total Signed",
        store=False,
        readonly=True,
        compute="_compute_amount",
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
        store=True,
        help="Utility field to express amount currency",
    )

    def action_payslip_done(self):
        if self.journal_id.edi_format_ids.code != "cfdi_1_2":
            return super().action_payslip_done()
        if any(slip.state == "cancel" for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))

        payslip_run_id = self.mapped("payslip_run_id")
        self._action_create_account_move()
        self.write({"state": "done"})
        payslip_run_id.action_close()

        self._action_create_account_move()
        return

    # --------------------------------------------------------------------------
    # Payroll Calculate
    # --------------------------------------------------------------------------

    def _compute_extratime_count(self):
        extratime_obj = self.env["hr.payroll.extratime.line"]
        for payslip in self:
            extratime_ids = extratime_obj.search(
                [
                    ("date", ">=", payslip.date_from),
                    ("date", "<=", payslip.date_to),
                    ("employee_id", "=", payslip.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )
            payslip.extratime_ids = extratime_ids
            payslip.extratime_count = len(extratime_ids)

    def _compute_amount(self):
        for payslip in self:
            allowance_total = 0.0
            deduction_total = 0.0
            other_payments = 0.0
            subtotal = 0.0
            discount = 0.0
            retentions = 0.0

            # Allowance Amount
            allowance_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "ALW"
            )
            for amount in allowance_obj:
                allowance_total += float(amount.total)
            payslip.allowance_total = allowance_total

            # Deduction Amount
            deduction_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "DED"
            )
            for amount in deduction_obj:
                deduction_total += float(amount.total)
            payslip.deduction_total = deduction_total

            # other_payments
            other_payments_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "OTPAY"
            )
            for amount in other_payments_obj:
                other_payments += float(amount.total)
            payslip.other_payments = other_payments

            # Amount Subtotal
            subtotal_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "NET"
                and line.salary_rule_id.code == "TALW"
            )
            for amount in subtotal_obj:
                subtotal += float(amount.total)
            payslip.amount_subtotal = subtotal

            # Discount
            discount_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "DED"
                and line.salary_rule_id.code != "D045"
            )
            for amount in discount_obj:
                discount += float(amount.total)
            payslip.discount = discount

            # Retentions
            retentions_obj = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "DED"
                and line.salary_rule_id.code == "D045"
            )
            for amount in retentions_obj:
                retentions += float(amount.total)
            payslip.retentions = retentions

            # Amount Total
            total_alw = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "NET"
                and line.salary_rule_id.code == "TALW"
            )
            total_ded = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "NET"
                and line.salary_rule_id.code == "TDED"
            )
            payslip.amount_total = total_alw.total - total_ded.total

    def _inverse_amount_total(self):
        for payslip in self:
            total_alw = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "NET"
                and line.salary_rule_id.code == "TALW"
            )
            total_ded = payslip.line_ids.filtered(
                lambda line: line.category_id.code == "NET"
                and line.salary_rule_id.code == "TDED"
            )
            payslip.amount_total = total_alw.total - total_ded.total

    def _l10n_mx_payroll_antiguedad(self):
        _l10n_mx_payroll_antiguedad = "P"
        for payslip in self:
            days = (payslip.date_to - payslip.contract_id.first_contract_date).days
            delta = relativedelta(
                payslip.date_to, payslip.contract_id.first_contract_date
            )

            if days // 7 <= 999:
                _l10n_mx_payroll_antiguedad += str(days // 7) + "W"
                return _l10n_mx_payroll_antiguedad

            if delta.years > 0:
                _l10n_mx_payroll_antiguedad += str(delta.years) + "Y"
            if delta.months > 0:
                _l10n_mx_payroll_antiguedad += str(delta.months) + "M"
            else:
                _l10n_mx_payroll_antiguedad += "0M"

            if delta.days > 0:
                _l10n_mx_payroll_antiguedad += str(delta.days) + "D"
            else:
                _l10n_mx_payroll_antiguedad += "0D"

        return _l10n_mx_payroll_antiguedad

    def calculate_isr(self, isr_type):
        _logger.info("calculate_isr  -->>>  " + str(self.id) + "  " + str(isr_type))
        localdict = self.env.context.get("force_payslip_localdict", None)
        if localdict is None:
            localdict = self._get_localdict()

        # Percepciones
        percepciones_grabadas_lines = self.env["hr.payslip.line"].search(
            ["|", ("category_id.code", "=", "ALW"), ("slip_id", "=", self.id)]
        )
        _logger.info(
            "percepciones_grabadas_lines   --->>>>  " + len(percepciones_grabadas_lines)
        )
        percepciones_excentas_lines = 0

        if percepciones_grabadas_lines:
            for line in percepciones_grabadas_lines:
                pass

                if line.salary_rule_id.exemption:
                    percepciones_excentas_lines += 1
                    if line.salary_rule_id.exempt_part:
                        localdict.update(
                            {"result": None, "result_qty": 1.0, "result_rate": 100}
                        )
                        exempt_value = line.salary_rule_id.exempt_part._compute_rule(
                            localdict
                        )

                    if line.salary_rule_id.taxable_part:
                        localdict.update(
                            {"result": None, "result_qty": 1.0, "result_rate": 100}
                        )
                        line.salary_rule_id.exempt_part._compute_rule(localdict)
        return exempt_value[0]

    def calculate_imss(self, imss_type):
        work_days = 0
        _logger.info(
            "-------------    calculate_imss    ------------------------------"
            + str(
                self.id,
            )
            + " "
            + str(imss_type)
        )

        full_days = 7  # self.imss_dias
        worked_days = full_days
        days_left = full_days

        param_config = self.env["ir.config_parameter"]

        if param_config.sudo().get_param("l10n_mx_hr_payroll.hr_payroll_uma_l10n_mx"):
            uma_id = param_config.sudo().get_param(
                "l10n_mx_hr_payroll.hr_payroll_uma_l10n_mx"
            )
            uma = self.env["hr.payroll.uma"].browse(int(uma_id)).daily

        if self.employee_id.employer_register.company_zone_l10n_mx == "z1":
            _logger.info("UMA   -->>  " + str(uma) + "  " + str(self.id))

        registered_days = self.env["hr.payslip.worked_days"].search(
            [("payslip_id", "=", self.id)]
        )
        if registered_days:
            for days in registered_days:
                if days.code == "FI" or days.code == "FJS":
                    worked_days = worked_days - days.number_of_days
                    days_left = days_left - days.number_of_days
                if (
                    days.code == "INC_MAT"
                    or days.code == "INC_EG"
                    or days.code == "INC_RT"
                ):
                    worked_days = worked_days - days.number_of_days
                    full_days = full_days - days.number_of_days
                if (
                    days.code == "WORK100"
                    or days.code == "FJC"
                    or days.code == "SEPT"
                    or days.code == "VAC"
                ):
                    work_days = work_days + days.number_of_days
        if work_days == 0:
            worked_days = 0
            full_days = 0

        base_cal = 0
        excess_base = 0

        if self.contract_id.sbc < 25 * uma:
            base_cal = self.contract_id.sbc
        else:
            base_cal = 25 * uma

        if base_cal > 3 * uma:
            excess_base = base_cal - 3 * uma

        if (
            self.employee_id.l10n_mx_hr_payroll_fiscal_regime == "02"
            or self.employee_id.l10n_mx_hr_payroll_fiscal_regime == "13"
        ):
            # IMSS Employee
            emp_excess_smg = round(full_days * 0.40 / 100 * excess_base, 2)
            emp_prest_cash = round(full_days * 0.375 / 100 * base_cal, 2)
            emp_sp_pens = round(full_days * 0.25 / 100 * base_cal, 2)
            emp_invalidez_vida = round(full_days * 0.625 / 100 * base_cal, 2)
            emp_cesantia_vejez = round(full_days * 1.125 / 100 * base_cal, 2)
            total_employee = round(
                emp_excess_smg
                + emp_prest_cash
                + emp_sp_pens
                + emp_invalidez_vida
                + emp_cesantia_vejez,
                2,
            )
            _logger.info("imss employee ----->>>" + str(total_employee))

            # IMSS Employer

            job_risk = self.employee_id.employer_register.job_risk_value
            pat_cuota_fija_pat = round(full_days * 20.40 / 100 * uma, 2)
            pat_exedente_smg = round(full_days * 1.10 / 100 * excess_base, 2)
            pat_prest_dinero = round(full_days * 1.05 / 100 * base_cal, 2)
            pat_esp_pens = round(full_days * 0.70 / 100 * base_cal, 2)
            pat_riesgo_trabajo = round(
                full_days * job_risk / 100 * base_cal, 2
            )  # falta
            pat_invalidez_vida = round(full_days * 1.75 / 100 * base_cal, 2)
            pat_guarderias = round(full_days * 1.00 / 100 * base_cal, 2)
            pat_retiro = round(days_left * 2.00 / 100 * base_cal, 2)
            pat_cesantia_vejez = round(worked_days * 3.150 / 100 * base_cal, 2)
            pat_infonavit = round(days_left * 5.0 / 100 * base_cal, 2)
            pat_total = (
                pat_cuota_fija_pat
                + pat_exedente_smg
                + pat_prest_dinero
                + pat_esp_pens
                + pat_riesgo_trabajo
                + pat_invalidez_vida
                + pat_guarderias
                + pat_retiro
                + pat_cesantia_vejez
                + pat_infonavit
            )

            _logger.info("IMSS Employer ----->>>  " + str(pat_total))
            _logger.info("Infonavit --------->>>  " + str(pat_infonavit))

        if imss_type == "employee":
            return total_employee
        elif imss_type == "company":
            return pat_total
        elif imss_type == "infonavit":
            return pat_infonavit
        else:
            raise ValidationError(_("You need to define the type of data imss"))

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------

    @api.model
    def get_payroll_dashboard_data(self, sections=None):
        # Entry point for getting the dashboard data
        # `sections` defines which part of the data we want to include/exclude
        if sections is None:
            sections = self._get_dashboard_default_sections()
        result = {}
        if "actions" in sections:
            # 'actions': -> Array of the different actions and their properties [
            #     {
            #         'string' -> Title for the line
            #         'count' -> Amount to display after the line
            #         'action' -> What to execute upon clicking the line
            #     }
            # ]
            # All actions can be either a xml_id or a dictionnary
            result["actions"] = self._get_dashboard_warnings()
        if "batches" in sections:
            # Batches are loaded for the last 3 months with batches,
            # for example if there are no batches for
            # the summer and september is loaded, we want to get september,
            # june, may.
            # Limit to max - 1 year
            batch_limit_date = fields.Date.today() - relativedelta(years=1, day=1)
            batch_group_read = (
                self.env["hr.payslip.run"]
                .with_context(lang="en_US")
                ._read_group(
                    [("date_start", ">=", batch_limit_date)],
                    fields=["date_start"],
                    groupby=["date_start:month"],
                    limit=20,
                    orderby="date_start desc",
                )
            )
            # Keep only the last 3 months
            batch_group_read = batch_group_read[:3]
            batch_group_read = False
            if batch_group_read:
                _logger.info("batch_group_read", batch_group_read)
                _logger.info(
                    "batch_group_read", batch_group_read[-1]["date_start:month"]
                )
                _logger.info(
                    "min_date",
                    datetime.strptime(
                        batch_group_read[-1]["date_start:month"], "%B %Y"
                    ),
                )
                min_date = datetime.strptime(
                    batch_group_read[-1]["date_start:month"], "%B %Y"
                )
                batches_read_result = self.env["hr.payslip.run"].search_read(
                    [("date_start", ">=", min_date)],
                    fields=self._get_dashboard_batch_fields(),
                )
                batches_read_result = self.env["hr.payslip.run"]
            else:
                batches_read_result = []
            translated_states = dict(
                self.env["hr.payslip.run"]
                ._fields["state"]
                ._description_selection(self.env)
            )
            for batch_read in batches_read_result:
                batch_read.update(
                    {
                        "name": f"{batch_read['name']} ({format_date(self.env, batch_read['date_start'], date_format='MM/y')})",  # noqa
                        "payslip_count": _(
                            "(%s Payslips)", batch_read["payslip_count"]
                        ),
                        "state": translated_states.get(
                            batch_read["state"], _("Unknown State")
                        ),
                    }
                )
            result["batches"] = batches_read_result
        if "notes" in sections:
            result["notes"] = {}
            # Fetch all the notes and their associated data
            dashboard_note_tag = self.env.ref(
                "hr_payroll.payroll_note_tag", raise_if_not_found=False
            )
            if dashboard_note_tag:
                # For note creation
                result["notes"].update(
                    {
                        "tag_id": dashboard_note_tag.id,
                    }
                )
        if "stats" in sections:
            result["stats"] = self._get_dashboard_stats()
        return result

    @api.onchange("hide_rule")
    def _onchange_hide_rule(self):
        for payslip in self:
            for line in payslip.line_ids:
                if not line.hide_rule and line.salary_rule_id.hide_rule:
                    line.hide_rule = True
                    continue
                if line.hide_rule and line.salary_rule_id.hide_rule:
                    line.hide_rule = False
                    continue

    def send_by_email(self):
        # OVERRIDE
        return super().send_by_email()

    def _get_base_local_dict(self):
        return {"float_round": float_round}

    def _get_localdict(self):
        self.ensure_one()
        worked_days_dict = {
            line.code: line for line in self.worked_days_line_ids if line.code
        }
        inputs_dict = {line.code: line for line in self.input_line_ids if line.code}

        employee = self.employee_id
        contract = self.contract_id

        localdict = {
            **self._get_base_local_dict(),
            **{
                "categories": BrowsableObject(employee.id, {}, self.env),
                "rules": BrowsableObject(employee.id, {}, self.env),
                "payslip": Payslips(employee.id, self, self.env),
                "worked_days": WorkedDays(employee.id, worked_days_dict, self.env),
                "inputs": InputLine(employee.id, inputs_dict, self.env),
                "employee": employee,
                "contract": contract,
                "result_rules": ResultRules(employee.id, {}, self.env),
            },
        }
        return localdict

    def _get_payslip_lines(self):
        line_vals = []
        for payslip in self:
            if not payslip.contract_id:
                raise UserError(
                    _(
                        "There's no contract set on payslip %(name)s for %(employee_id.name)s."
                        "Check that there is at least a contract set on the employee form.",
                        payslip.name,
                        payslip.employee_id.name,
                    )
                )

            localdict = self.env.context.get("force_payslip_localdict", None)
            if localdict is None:
                localdict = payslip._get_localdict()

            rules_dict = localdict["rules"].dict
            result_rules_dict = localdict["result_rules"].dict
            blacklisted_rule_ids = self.env.context.get(
                "prevent_payslip_computation_line_ids", []
            )

            result = {}

            for rule in sorted(self.struct_id.rule_ids, key=lambda x: x.sequence):
                if rule.id in blacklisted_rule_ids:
                    continue
                localdict.update(
                    {"result": None, "result_qty": 1.0, "result_rate": 100}
                )
                if rule._satisfy_condition(localdict):
                    amount, qty, rate = rule._compute_rule(localdict)
                    # check if there is already a rule computed with that code
                    previous_amount = (
                        rule.code in localdict and localdict[rule.code] or 0.0
                    )
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    result_rules_dict[rule.code] = {
                        "total": tot_rule,
                        "amount": amount,
                        "quantity": qty,
                    }
                    rules_dict[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = rule.category_id._sum_salary_rule_category(
                        localdict, tot_rule - previous_amount
                    )
                    # Retrieve the line name in the employee's lang
                    employee_lang = payslip.employee_id.sudo().address_home_id.lang
                    # This actually has an impact, don't remove this line
                    context = {"lang": employee_lang}  # noqa
                    if rule.code in [
                        "BASIC",
                        "GROSS",
                        "NET",
                    ]:  # Generated by default_get (no xmlid)
                        continue
                    else:
                        rule_name = rule.with_context(lang=employee_lang).name
                    # create/overwrite the rule in the temporary results
                    hide_rule = False
                    if rule.hide_rule:
                        hide_rule = True
                    result[rule.code] = {
                        "sequence": rule.sequence,
                        "code": rule.code,
                        "name": rule_name,
                        "note": rule.note,
                        "hide_rule": hide_rule,
                        "salary_rule_id": rule.id,
                        "contract_id": localdict["contract"].id,
                        "employee_id": localdict["employee"].id,
                        "amount": amount,
                        "quantity": qty,
                        "rate": rate,
                        "slip_id": payslip.id,
                    }
            line_vals += list(result.values())
        return line_vals

    def action_view_extratime(self, extratime=False):
        if not extratime:
            self.sudo()._read(["extratime_ids"])
            extratime = self.extratime_ids
        result = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_mx_hr_payroll.action_view_hr_extratime_movement"
        )
        if len(extratime) > 1:
            result["domain"] = [("id", "in", extratime.ids)]
        elif len(extratime) == 1:
            res = self.env.ref("hr.payroll.extratime.line", False)
            form_view = [(res and res.id or False, "form")]
            if "views" in result:
                result["views"] = form_view + [
                    (state, view) for state, view in result["views"] if view != "form"
                ]
            else:
                result["views"] = form_view
            result["res_id"] = extratime.id
        else:
            result = {"type": "ir.actions.act_window_close"}

        return result
