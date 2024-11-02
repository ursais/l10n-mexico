import base64
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HrPayrollIDSEReports(models.Model):
    _name = "hr.payroll.idse.reports"
    _description = "Payroll IDSE Reports"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    date_start = fields.Date()
    date_end = fields.Date()
    report_type = fields.Selection(
        [
            ("alta", "IDSE Alta"),
            ("baja", "IDSE Baja"),
            ("mod_wage", "IDSE modificacion Salarial"),
        ]
    )
    line_ids = fields.One2many(
        "hr.payroll.idse.reports.line", "line_id", string="Payment Lines"
    )
    notes = fields.Html()
    movs_count = fields.Integer(compute="_compute_movs_count")
    txt_file = fields.Binary("txt file")
    attachment_id = fields.Many2one(
        "ir.attachment", string="Attachment", help="Attachment"
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    def _compute_movs_count(self):
        for movs in self:
            movs.movs_count = len(movs.line_ids)

    def action_open_payroll_movs_idse(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payroll.idse.reports.line",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.line_ids.ids]],
            "name": "Payroll Movements of IDSE",
        }

    @api.model_create_multi
    def create(self, vals):
        _logger.warning(str(vals))
        if "company_id" in vals:
            self = self.with_company(vals["company_id"])
        result = super().create(vals)
        return result

    def write(self, vals):
        _logger.warning(str(vals))
        return super().write(vals)

    @api.onchange("report_type", "date_start", "date_end", "name")
    def _onchange_name(self):
        for idse in self:
            _logger.warning(
                str(idse.report_type)
                + " +  "
                + str(idse.date_start)
                + " + "
                + str(idse.date_end)
            )
            if idse.report_type == "alta":
                idse.name = "Reporte de IDSE Alta "
            elif idse.report_type == "baja":
                idse.name = "Reporte de IDSE Baja "
            elif idse.report_type == "mod_wage":
                idse.name = "Reporte de IDSE Modificacion Salarial "
            else:
                idse.name = ""

    def idse_done(self):
        for idse in self:
            idse.state = "done"
            self.message_post(body=_("Payroll IDSE Report has been Calculated"))
            return True

    def idse_cancel(self):
        for idse in self:
            idse.state = "cancel"
            self.message_post(body=_("Payroll IDSE Report has been Calculated"))
            return True

    def idse_back_to_draft(self):
        for idse in self:
            idse.state = "draft"
            self.message_post(body=_("Payroll IDSE Report has been draft"))
            return True

    def idse_calculate(self):
        for idse in self:
            idse.state = "calculated"
            date_start = idse.date_start
            date_end = idse.date_end

            if idse.report_type == "alta":
                idse.name = "Reporte de IDSE Alta "
                contract_ids = self.env["hr.contract"].search(
                    [
                        "&",
                        "&",
                        ("date_start", ">=", date_start),
                        ("date_start", "<=", date_end),
                        ("state", "=", "open"),
                        ("company_id", "=", idse.company_id.id),
                    ]
                )
                idse.line_ids.unlink()
                for contract_id in contract_ids:
                    _logger.warning("Contract -->>  " + str(contract_id.id))
                    self.env["hr.payroll.idse.reports.line"].create(
                        {
                            "line_id": idse.id,
                            "date": fields.Date.context_today(self),
                            "name": contract_id.employee_id.id,
                            "contract_id": contract_id.id,
                            "ssnid": contract_id.employee_id.ssnid,
                            "company_id": idse.company_id.id,
                        }
                    )
            elif idse.report_type == "baja":
                idse.name = "Reporte de IDSE Baja "
                contract_ids = self.env["hr.contract"].search(
                    [
                        "&",
                        "&",
                        ("date_end", ">=", date_start),
                        ("date_end", "<=", date_end),
                        ("state", "=", "cancel"),
                        ("company_id", "=", idse.company_id.id),
                    ]
                )
                idse.line_ids.unlink()
                for contract_id in contract_ids:
                    self.env["hr.payroll.idse.reports.line"].create(
                        {
                            "line_id": idse.id,
                            "date": fields.Date.context_today(self),
                            "name": contract_id.employee_id.id,
                            "contract_id": contract_id.id,
                            "ssnid": contract_id.employee_id.ssnid,
                            "company_id": idse.company_id.id,
                        }
                    )
            elif idse.report_type == "mod_wage":
                idse.name = "Reporte de IDSE Modificación Salarial "
                salary_history_ids = self.env["hr.contract.salary_history"].search(
                    [
                        "&",
                        "&",
                        ("state", "=", "applied"),
                        ("date_applied", ">=", idse.date_start),
                        ("date_applied", "<=", idse.date_end),
                    ]
                )
                idse.line_ids.unlink()
                for history_line in salary_history_ids:
                    self.env["hr.payroll.idse.reports.line"].create(
                        {
                            "line_id": idse.id,
                            "date": fields.Date.context_today(self),
                            "name": history_line.contract_id.employee_id.id,
                            "contract_id": history_line.contract_id.id,
                            "ssnid": history_line.contract_id.employee_id.ssnid,
                            "company_id": idse.company_id.id,
                        }
                    )
            else:
                idse.name = ""

            idse.message_post(body=_("Payroll IDSE Report has been Calculated"))
            return True

    def idse_txt(self):
        data = ""
        lines = ""

        for idse in self:
            if idse.report_type == "alta":
                for line in self.line_ids:
                    data = [""] * 19
                    data[0] = line.name.employer_register.name
                    data[1] = line.name.ssnid.zfill(11)
                    data[2] = str(line.name.lastname).upper() + " " * (
                        27 - len(str(line.name.lastname))
                    )
                    data[3] = str(line.name.second_lastname).upper() + " " * (
                        27 - len(str(line.name.second_lastname))
                    )
                    data[4] = str(line.name.firstname).upper() + " " * (
                        27 - len(str(line.name.firstname))
                    )
                    data[5] = (
                        format(line.name.contract_id.sdi, ".2f")
                        .replace(".", "")
                        .zfill(6)
                    )
                    data[6] = " " * 6
                    data[7] = "1"
                    data[8] = str(line.name.contract_id.salary_type)[1:]
                    data[9] = "0"
                    data[10] = (
                        str(line.contract_id.date_start.strftime("%d"))
                        + str(line.contract_id.date_start.strftime("%m"))
                        + str(line.contract_id.date_start.strftime("%Y"))
                    )
                    data[11] = str(line.name.umf).zfill(3)
                    data[12] = " " * 2
                    data[13] = "08"
                    data[14] = "01406"
                    data[15] = str(line.name.employee_number).zfill(10)
                    data[16] = " "
                    data[17] = str(line.name.address_home_id.curp).upper()
                    data[18] = "9"

                    lines += "".join(str(d) for d in data) + "\n"

                data_end = [""] * 7
                data_end[0] = "*" * 13
                data_end[1] = " " * 43
                data_end[2] = "000001"
                data_end[3] = " " * 71
                data_end[4] = "01406"
                data_end[5] = " " * 29
                data_end[6] = "9"

                lines += "".join(str(d) for d in data_end)
                self.txt_file = base64.b64encode(lines.encode())
                return {
                    "type": "ir.actions.act_url",
                    "url": "/web/content/hr.payroll.idse.reports/%s/txt_file/%s?download=true"
                    % (self.id, "alta.txt"),
                    "target": "self",
                }

            elif idse.report_type == "baja":
                for line in self.line_ids:
                    data = [""] * 19
                    data[0] = line.name.employer_register.name
                    data[1] = line.name.ssnid.zfill(11)
                    data[2] = str(line.name.lastname).upper()
                    data[3] = " " * (27 - len(data[2]))
                    data[4] = str(line.name.second_lastname).upper()
                    data[5] = " " * (27 - len(data[4]))
                    data[6] = str(line.name.firstname).upper()
                    data[7] = " " * (27 - len(data[6]))
                    data[8] = "0" * 15
                    data[9] = str(line.contract_id.date_end)[-2:]
                    data[10] = str(line.contract_id.date_end)[5:7]
                    data[11] = str(line.contract_id.date_end)[:4]
                    data[12] = " " * 5
                    data[13] = "02"
                    data[14] = "01406"
                    data[15] = str(line.name.employee_number).zfill(10)
                    data[16] = "2"
                    data[17] = " " * 18
                    data[18] = "9"

                    lines += "".join(str(d) for d in data) + "\n"

                data_end = [""] * 7
                data_end[0] = "*" * 13
                data_end[1] = " " * 43
                data_end[2] = "000001"
                data_end[3] = " " * 71
                data_end[4] = "01406"
                data_end[5] = " " * 29
                data_end[6] = "9"

                lines += "".join(str(d) for d in data_end)
                self.txt_file = base64.b64encode(lines.encode())
                return {
                    "type": "ir.actions.act_url",
                    "url": "/web/content/hr.payroll.idse.reports/%s/txt_file/%s?download=true"
                    % (self.id, "baja.txt"),
                    "target": "self",
                }

            if idse.report_type == "mod_wage":
                for line in self.line_ids:
                    date = sorted(
                        line.name.contract_id.salary_history_ids,
                        key=lambda x: x.date_applied,
                        reverse=True,
                    )[0]
                    data = [""] * 21
                    data[0] = line.name.employer_register.name
                    data[1] = line.name.ssnid.zfill(11)
                    data[2] = str(line.name.lastname).upper()
                    data[3] = " " * (27 - len(data[2]))
                    data[4] = str(line.name.second_lastname).upper()
                    data[5] = " " * (27 - len(data[4]))
                    data[6] = str(line.name.firstname).upper()
                    data[7] = " " * (27 - len(data[6]))
                    data[8] = (
                        format(line.name.contract_id.sdi, ".2f")
                        .replace(".", "")
                        .zfill(6)
                    )
                    data[9] = "0" * 7
                    data[10] = str(line.name.contract_id.salary_type)[1:]
                    data[11] = "0"
                    data[12] = str(date.date_applied)[-2:]
                    data[13] = str(date.date_applied)[5:7]
                    data[14] = str(date.date_applied)[:4]
                    data[15] = " " * 5
                    data[16] = "0701406"
                    data[17] = str(line.name.employee_number).zfill(10)
                    data[18] = " "
                    data[19] = line.name.address_home_id.curp
                    data[20] = "9"

                    lines += "".join(str(d) for d in data) + "\n"

                data_end = [""] * 7
                data_end[0] = "*" * 13
                data_end[1] = " " * 43
                data_end[2] = "000001"
                data_end[3] = " " * 71
                data_end[4] = "01406"
                data_end[5] = " " * 29
                data_end[6] = "9"

                lines += "".join(str(d) for d in data_end)
                self.txt_file = base64.b64encode(lines.encode())
                return {
                    "type": "ir.actions.act_url",
                    "url": "/web/content/hr.payroll.idse.reports/%s/txt_file/%s?download=true"
                    % (self.id, "mod_sal.txt"),
                    "target": "self",
                }


class HrPayrollIDSEReportsLine(models.Model):
    _name = "hr.payroll.idse.reports.line"
    _description = "Payroll IDSE Reports Line"

    line_id = fields.Many2one(
        "hr.payroll.idse.reports", required=True, ondelete="cascade"
    )
    name = fields.Many2one("hr.employee")
    date = fields.Date()
    contract_id = fields.Many2one("hr.contract")
    ssnid = fields.Char(string="NSS")
    amount = fields.Float()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("paid", "Paid"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )
    company_id = fields.Many2one("res.company")
