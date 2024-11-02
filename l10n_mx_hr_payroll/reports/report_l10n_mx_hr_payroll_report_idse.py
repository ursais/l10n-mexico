import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ReportL10nMxHrPayrollReportIdse(models.AbstractModel):
    _name = "report.l10n_mx_hr_payroll.report_idse"
    _template = "l10n_mx_hr_payroll.report_idse"
    _description = "IDSE (IMSS) Report"

    filter_date = {"mode": "range", "filter": "this_month"}

    def _get_contract_type_idse_baja(self, contract_ids, options):
        for record in contract_ids:
            if record.contract_type == "01":
                if not options.get("update_salaries_txt", False):
                    return "Trabajador Permanente"
                else:
                    return "1"
            elif record.contract_type == "02":
                if not options.get("update_salaries_txt", False):
                    return "Trabajador Eventual"
                else:
                    return "2"
            elif record.contract_type == "03":
                if not options.get("update_salaries_txt", False):
                    return "Trabajador eventual de la construccion"
                else:
                    return "3"
            elif record.contract_type == "04":
                if not options.get("update_salaries_txt", False):
                    return "Trabajador eventual del campo"
                else:
                    return "4"
            else:
                raise UserError(
                    _(
                        "You need to set the contract type for the employee (%("
                        "record.employee_id.name)s)."
                    )
                )

    def _get_salary_type_idse_baja(self, contract_ids, options):
        for record in contract_ids:
            if record.salary_type == "01":
                if not options.get("update_salaries_txt", False):
                    return "Fijo"
                else:
                    return "0"
            elif record.salary_type == "02":
                if not options.get("update_salaries_txt", False):
                    return "Variable"
                else:
                    return "1"
            elif record.salary_type == "03":
                if not options.get("update_salaries_txt", False):
                    return "Mixto"
                else:
                    return "2"
            else:
                raise UserError(
                    _(
                        "You need to set the salary type for the employee (%("
                        "record.employee_id.name)s)."
                    )
                )

    def _get_journal_type_idse_baja(self, contract_ids, options):
        for record in contract_ids:
            if record.journal_type == "00":
                if not options.get("update_salaries_txt", False):
                    return "Normal"
                else:
                    return "0"
            elif record.journal_type == "01":
                return "Un Dia"
            elif record.journal_type == "02":
                return "Dos Dias"
            elif record.journal_type == "03":
                return "Tres Dias"
            elif record.journal_type == "04":
                return "Cuatro Dias"
            elif record.journal_type == "05":
                return "Cinco Dias"
            elif record.journal_type == "06":
                return "Jornada Reducida"
            else:
                raise UserError(
                    _(
                        "You need to set the Journal type for employee "
                        "(%(record.employee_id.name)s)"
                    )
                )

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        context = self.env.context
        contract_ids = self.env["hr.contract"].search(
            [
                ("state", "=", "cancel"),
                ("date_start", ">=", context["date_from"]),
                ("date_start", "<=", context["date_to"]),
            ]
        )
        if not contract_ids:
            return lines

        contract_type = self._get_contract_type_idse_baja(contract_ids, options)

        salary_type = self._get_salary_type_idse_baja(contract_ids, options)

        journal_type = self._get_journal_type_idse_baja(contract_ids, options)

        for record in contract_ids:
            curp = record.employee_id.address_home_id.curp

            if options.get("update_salaries_txt", False):
                reg_date = (record.date_start).strftime("%d%m%Y")
            else:
                reg_date = (record.date_start).strftime("%d-%m-%Y")

            sbc = 0
            sbc = (str(f"{record.sdi:4.2f}").replace(".", "")).zfill(6)

            if options.get("update_salaries_txt", False):
                columns = [
                    record.employee_id.employer_register.name,
                    "1",
                    record.employee_id.ssnid,
                    "1",
                    record.employee_id.lastname,
                    record.employee_id.second_lastname,
                    record.employee_id.firstname,
                    sbc,
                    contract_type,
                    salary_type,
                    journal_type,
                    reg_date,
                    record.employee_id.employee_number,
                    curp,
                ]
            else:
                columns = [
                    record.employee_id.employer_register.name,
                    record.employee_id.ssnid,
                    f"{record.sdi:10.2f}",
                    contract_type,
                    salary_type,
                    journal_type,
                    reg_date,
                    record.employee_id.umf,
                    "00000",
                    record.employee_id.employee_number,
                    curp,
                ]
            lines.append(
                {
                    "id": str(record["id"]),
                    "name": str(record.employee_id.name),
                    "columns": [{"name": v} for v in columns],
                    "level": 2,
                    "unfoldable": False,
                    "unfolded": True,
                }
            )
        return lines

    employee_id = fields.Many2one("hr.employee")
    name = fields.Char(string="Employer Register")
    date = fields.Date()
    sbc = fields.Float()
    employee_type = fields.Char()

    def preview_button(self):
        for _rec in self:
            return True

    def _get_report_name(self):
        return _("IDSE (report)")

    def _get_reports_buttons(self):
        return [
            {
                "name": _("Print Preview"),
                "sequence": 1,
                "action": "print_pdf",
                "file_export_type": _("PDF"),
            },
            {
                "name": _("Export (XLSX)"),
                "sequence": 2,
                "action": "print_xlsx",
                "file_export_type": _("XLSX"),
            },
            {
                "name": _("Export IMSS (TXT)"),
                "sequence": 3,
                "action": "print_txt",
                "file_export_type": _("IDSE"),
            },
        ]

    def _get_columns_name(self, options):
        columns = [
            {},
            {"name": _("Employer Register")},
            {"name": _("NSS")},
            {"name": _("SBC"), "class": "number"},
            {"name": _("Employee Type")},
            {"name": _("Salary Type")},
            {"name": _("Journal Type")},
            {"name": _("Date")},
            {"name": _("UMF")},
            {"name": _("Guia")},
            {"name": _("Employee Code")},
            {"name": _("CURP")},
        ]
        return columns

    def get_txt(self, options):
        ctx = self._set_context(options)
        ctx.update({"no_format": True, "print_mode": True, "raise": True})
        options["update_salaries_txt"] = True
        context = self.env.context
        _logger.info("context _get_text--->>>>   ", self, context)
        return self.with_context(
            **ctx
        )._l10n_mx_hr_payroll_idse_update_salary_txt_export(options)

    def _l10n_mx_hr_payroll_idse_altas_reingreso_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ""
        for line in txt_data:
            if not line.get("id"):
                continue
            columns = line.get("columns", [])
            data = [""] * 20
            data[0] = columns[0]["name"]
            data[1] = columns[1]["name"]
            data[2] = columns[2]["name"]
            data[3] = columns[3]["name"]
            data[4] = columns[4]["name"]
            data[5] = columns[5]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[7] = columns[7]["name"]
            data[8] = columns[8]["name"]
            data[9] = columns[9]["name"]
            data[10] = columns[10]["name"]
            data[11] = columns[11]["name"]
            data[12] = " " * 5
            data[13] = "07"
            data[14] = "00000"
            data[15] = columns[12]["name"]
            data[16] = " "
            data[17] = columns[13]["name"]
            data[18] = "0"

            lines += "|".join(str(d) for d in data) + "\n"
        return lines

    def _l10n_mx_hr_payroll_idse_baja_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ""
        for line in txt_data:
            if not line.get("id"):
                continue
            columns = line.get("columns", [])
            data = [""] * 20
            data[0] = columns[0]["name"]
            data[1] = columns[1]["name"]
            data[2] = columns[2]["name"]
            data[3] = columns[3]["name"]
            data[4] = columns[4]["name"]
            data[5] = columns[5]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[7] = columns[7]["name"]
            data[8] = columns[8]["name"]
            data[9] = columns[9]["name"]
            data[10] = columns[10]["name"]
            data[11] = columns[11]["name"]
            data[12] = " " * 5
            data[13] = "07"
            data[14] = "00000"
            data[15] = columns[12]["name"]
            data[16] = " "
            data[17] = columns[13]["name"]
            data[18] = "0"

            lines += "|".join(str(d) for d in data) + "\n"
        return lines

    def _l10n_mx_hr_payroll_idse_update_salary_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ""
        for line in txt_data:
            if not line.get("id"):
                continue
            columns = line.get("columns", [])
            data = [""] * 20
            data[0] = columns[0]["name"]
            data[1] = columns[1]["name"]
            data[2] = columns[2]["name"]
            data[3] = columns[3]["name"]
            data[4] = columns[4]["name"]
            data[5] = columns[5]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[6] = columns[6]["name"]
            data[7] = columns[7]["name"]
            data[8] = columns[8]["name"]
            data[9] = columns[9]["name"]
            data[10] = columns[10]["name"]
            data[11] = columns[11]["name"]
            data[12] = " " * 5
            data[13] = "07"
            data[14] = "00000"
            data[15] = columns[12]["name"]
            data[16] = " "
            data[17] = columns[13]["name"]
            data[18] = "0"

            lines += "|".join(str(d) for d in data) + "\n"
        return lines
