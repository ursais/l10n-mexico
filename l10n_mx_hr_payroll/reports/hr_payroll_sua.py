import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HrPayrollSUAReport(models.AbstractModel):
    _name = "hr.payroll.sua.html.report"
    _description = "SUA ( IMSS ) Report"
    # _inherit = "account.report"

    filter_date = {"mode": "range", "filter": "this_month"}

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        employee_ids = self.env["hr.employee"].search([])
        if not employee_ids:
            return lines

        for record in employee_ids:
            columns = [
                record["employer_register"].name,
                record["ssnid"],
                record["ssnid"],
                "23051975",
                "Cordoba",
                "Cordoba",
                "50",
                "",
                "m",
                "Fijo",
            ]
            lines.append(
                {
                    "id": str(record["id"]),
                    "name": str(record["name"]),
                    "columns": [{"name": v} for v in columns],
                    "level": 2,
                    "unfoldable": False,
                    "unfolded": True,
                }
            )
        return lines

    def _get_bimonth_name(self, bimonth_index):
        bimonth_names = {
            1: "Enero - Febrero",
            2: "Marzo - Abril",
            3: "Mayo - Junio",
            4: "Julio - Agosto",
            5: "Septiembre - Octubre",
            6: "Noviembre - Diciembre",
        }
        return bimonth_names[bimonth_index]

    employee_id = fields.Many2one("hr.employee")
    name = fields.Char(string="Employer Register")
    date = fields.Date()
    sbc = fields.Float()
    employee_type = fields.Char()

    def preview_button(self):
        for _rec in self:
            return True

    def _get_report_name(self):
        return _("IDSE (Reingresos)")

    def _get_reports_buttons(self):
        buttons = super()._get_reports_buttons()
        buttons += [
            {
                "name": _("Export IMSS (TXT)"),
                "sequence": 3,
                "action": "print_txt",
                "file_export_type": _("SUA"),
            }
        ]
        return buttons

    def _get_columns_name(self, options):
        columns = [
            {},
            {"name": _("Employer Register")},
            {"name": _("NSS")},
            {"name": _("Postal Code")},
            {"name": _("Date Birthday")},
            {"name": _("Place of birth")},
            {"name": _("State of birth")},
            {"name": _("UMF")},
            {"name": _("Occupation")},
            {"name": _("Sex")},
            {"name": _("Salary type")},
        ]
        return columns

    def _get_values_for_columns(self, values):
        return [
            {"name": values["name"], "field_name": "name"},
            {
                "name": self.format_value(values["tax_base_amount"]),
                "field_name": "tax_base_amount",
            },
            {
                "name": self.format_value(values["balance_15_over_19"]),
                "field_name": "balance_15_over_19",
            },
            {"name": self.format_value(values["balance"]), "field_name": "balance"},
            {"name": 0.15 if values["balance"] else 0, "field_name": "percentage"},
        ]

    def get_txt(self, options):
        ctx = self._set_context(options)
        ctx.update({"no_format": True, "print_mode": True, "raise": True})
        return self.with_context(
            **ctx
        )._l10n_mx_hr_payroll_sua_update_salary_txt_export(options)

    def _l10n_mx_hr_payroll_sua_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ""
        for line in txt_data:
            _logger.info("txt_data", line["name"])
            if not line.get("id"):
                continue
            columns = line.get("columns", [])
            _logger.info("columns", columns)
            data = [""] * 25
            data[0] = line["name"]
            data[1] = columns[0]["name"]
            data[2] = columns[1]["name"]
            lines += "|".join(str(d) for d in data) + "\n"
        return lines
