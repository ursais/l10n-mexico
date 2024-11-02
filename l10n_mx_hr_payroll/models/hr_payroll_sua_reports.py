import base64
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HrPayrollSUAReports(models.Model):
    _name = "hr.payroll.sua.reports"
    _description = "Payroll SUA Reports"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    date_start = fields.Date()
    date_end = fields.Date()
    report_type = fields.Selection(
        [
            ("alta", "SUA Registration"),
            ("movt", "SUA Movements"),
        ]
    )
    movt_type = fields.Selection(
        [
            ("02", "Deregistration"),
            ("07", "Salary Modification"),
            ("08", "Reinstatement"),
            ("11", "Absenteeism"),
            ("12", "Incapacity"),
        ],
        default="02",
        string="Movement Type",
    )
    line_ids = fields.One2many(
        "hr.payroll.sua.reports.line", "line_id", string="Payment Lines"
    )
    notes = fields.Html()
    movs_count = fields.Integer(compute="_compute_movs_count")
    txt_file = fields.Binary("txt file")
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

    def action_open_payroll_movs_sua(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payroll.sua.reports.line",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.line_ids.ids]],
            "name": "Payroll Movements of SUA",
        }

    @api.onchange("report_type", "date_start", "date_end", "name", "movt_type")
    def _onchange_name(self):
        for sua in self:
            if sua.report_type == "alta":
                sua.name = "SUA Report - Registration "
            elif sua.report_type == "movt":
                sua.name = "SUA Report - Movements "
            elif sua.report_type == "movt" and sua.movt_type == "08":
                sua.name = "SUA Report - Reinstatement"
            else:
                sua.name = ""

    def sua_done(self):
        for sua in self:
            sua.state = "done"
            sua.message_post(body=_("Payroll SUA Report has been Calculated"))
            return True

    def sua_cancel(self):
        for sua in self:
            sua.state = "cancel"
            sua.message_post(body=_("Payroll SUA Report has been Cancelled"))
            return True

    def sua_calculate(self):
        for sua in self:
            sua.state = "calculated"
            date_start = sua.date_start
            date_end = sua.date_end

            if sua.report_type == "alta":
                sua.name = "SUA Report- Registration "
                contract_ids = self.env["hr.contract"].search(
                    [
                        "&",
                        "&",
                        ("date_start", ">=", date_start),
                        ("date_start", "<=", date_end),
                        ("state", "=", "open"),
                        ("company_id", "=", sua.company_id.id),
                    ]
                )
                sua.line_ids.unlink()
                for contract_id in contract_ids:
                    line = self.env["hr.payroll.sua.reports.line"].create(
                        {
                            "line_id": sua.id,
                            "date": fields.Date.context_today(self),
                            "name": contract_id.employee_id.id,
                            "contract_id": contract_id.id,
                            "ssnid": contract_id.employee_id.ssnid,
                            "company_id": sua.company_id.id,
                        }
                    )
            elif sua.report_type == "movt":
                self.movements(sua)
            else:
                sua.name = "SUA Report - without specifying the type of movement"

            sua.message_post(body=_("Payroll SUA Report has been Calculated"))
            return True

    def movements(self, sua):
        if sua.movt_type == "02":
            sua.name = "SUA Report - Deregistration "
            contract_ids = self.env["hr.contract"].search(
                [
                    "&",
                    ("date_end", ">=", sua.date_start),
                    ("date_end", "<=", sua.date_end),
                    ("state", "=", "cancel"),
                ]
            )
            self.line_ids.unlink()
            for contract_id in contract_ids:
                self.env["hr.payroll.sua.reports.line"].create(
                    {
                        "line_id": self.id,
                        "date": fields.Date.context_today(self),
                        "name": contract_id.employee_id.id,
                        "contract_id": contract_id.id,
                        "ssnid": contract_id.employee_id.ssnid,
                        "company_id": sua.company_id.id,
                    }
                )
        if self.movt_type == "07":
            sua.name = "SUA Report - Salary Modification"
            sua.line_ids.unlink()
            salary_history_ids = self.env["hr.contract.salary_history"].search(
                [
                    "&",
                    "&",
                    ("state", "=", "applied"),
                    ("date_applied", ">=", sua.date_start),
                    ("date_applied", "<=", sua.date_end),
                ]
            )
            sua.line_ids.unlink()
            for salary_id in salary_history_ids:
                self.env["hr.payroll.sua.reports.line"].create(
                    {
                        "line_id": sua.id,
                        "date": salary_id.date_applied,
                        "name": salary_id.employee_id.id,
                        "contract_id": salary_id.contract_id.id,
                        "ssnid": salary_id.employee_id.ssnid,
                        "company_id": sua.company_id.id,
                    }
                )
        if sua.movt_type == "08":
            sua.name = "SUA Report- Reinstatement"
            contract_ids = self.env["hr.contract"].search(
                [
                    "&",
                    "&",
                    ("date_start", ">=", sua.date_start),
                    ("date_start", "<=", sua.date_end),
                    ("state", "=", "open"),
                    ("company_id", "=", sua.company_id.id),
                ]
            )
            contract_olders_ids = self.env["hr.contract"].search(
                [
                    ("state", "in", ["cancel", "close"]),
                    ("company_id", "=", sua.company_id.id),
                ]
            )
            sua.line_ids.unlink()
            if contract_ids and contract_olders_ids:
                for contract_id in contract_ids:
                    self.env["hr.payroll.sua.reports.line"].create(
                        {
                            "line_id": sua.id,
                            "date": fields.Date.context_today(self),
                            "name": contract_id.employee_id.id,
                            "contract_id": contract_id.id,
                            "ssnid": contract_id.employee_id.ssnid,
                            "company_id": sua.company_id.id,
                        }
                    )
        if sua.movt_type == "11":
            sua.name = "SUA Report - Absenteeism"
            timeoff_ids = self.env["hr.leave"].search(
                [
                    "&",
                    "&",
                    ("state", "=", "validate"),
                    ("request_date_from", ">=", sua.date_start),
                    ("request_date_to", "<=", sua.date_end),
                ]
            )
            sua.line_ids.unlink()
            if timeoff_ids:
                for timeoff_id in timeoff_ids:
                    if (
                        timeoff_id.holiday_status_id.time_type == "leave"
                        and not timeoff_id.holiday_status_id.disabilities_type
                    ):
                        self.env["hr.payroll.sua.reports.line"].create(
                            {
                                "line_id": sua.id,
                                "date": timeoff_id.request_date_from,
                                "name": timeoff_id.employee_id.id,
                                "contract_id": False,
                                "timeoff_id": timeoff_id.id,
                                "ssnid": timeoff_id.employee_id.ssnid,
                                "company_id": sua.company_id.id,
                            }
                        )
        if sua.movt_type == "12":
            sua.name = "SUA Report - Incapacity"
            timeoff_ids = self.env["hr.leave"].search(
                [
                    "&",
                    "&",
                    ("state", "=", "validate"),
                    ("request_date_from", ">=", sua.date_start),
                    ("request_date_to", "<=", sua.date_end),
                ]
            )
            sua.line_ids.unlink()
            if timeoff_ids:
                for timeoff_id in timeoff_ids:
                    if (
                        timeoff_id.holiday_status_id.time_type == "leave"
                        and timeoff_id.holiday_status_id.disabilities_type
                    ):
                        self.env["hr.payroll.sua.reports.line"].create(
                            {
                                "line_id": sua.id,
                                "date": timeoff_id.request_date_from,
                                "name": timeoff_id.employee_id.id,
                                "contract_id": False,
                                "timeoff_id": timeoff_id.id,
                                "ssnid": timeoff_id.employee_id.ssnid,
                                "company_id": sua.company_id.id,
                            }
                        )

    def sua_back_to_draft(self):
        for sua in self:
            sua.state = "draft"
            sua.message_post(body=_("Payroll SUA Report has been draft"))
            return True

    def sua_txt(self):
        data = ""
        lines = ""

        for sua in self:
            if sua.report_type == "alta":
                for line in self.line_ids:
                    len_name = (
                        len(str(line.name.lastname))
                        + len(str(line.name.second_lastname))
                        + len(str(line.name.firstname))
                    )
                    data = [""] * 14
                    data[0] = line.name.employer_register.name
                    data[1] = line.name.ssnid.zfill(11)
                    data[2] = str(line.name.address_home_id.vat).upper()
                    data[3] = str(line.name.address_home_id.curp).upper()
                    data[4] = (
                        str(line.name.lastname).upper()
                        + "$"
                        + str(line.name.second_lastname).upper()
                        + "$"
                        + str(line.name.firstname).upper()
                        + (" " * (48 - len_name))
                    )
                    data[5] = "1"
                    data[6] = "0"
                    data[7] = (
                        str(line.contract_id.date_start.strftime("%d"))
                        + str(line.contract_id.date_start.strftime("%m"))
                        + str(line.contract_id.date_start.strftime("%Y"))
                    )
                    data[8] = (
                        format(line.name.contract_id.sdi, ".2f")
                        .replace(".", "")
                        .zfill(7)
                    )
                    data[9] = line.name.employee_number.zfill(17)
                    data[10] = " " * 10
                    data[11] = "0" * 8
                    data[12] = "0"
                    data[13] = "0" * 8

                    lines += "".join(str(d) for d in data) + "\n"

                self.txt_file = base64.b64encode(lines.encode())
                return {
                    "type": "ir.actions.act_url",
                    "url": "/web/content/hr.payroll.sua.reports/"
                    + "%s/txt_file/%s?download=true" % (self.id, "aseg.txt"),
                    "target": "self",
                }
            elif sua.report_type == "movt":
                if sua.movt_type == "02":
                    for line in self.line_ids:
                        data = [""] * 7
                        data[0] = line.name.employer_register.name
                        data[1] = line.name.ssnid.zfill(11)
                        data[2] = "02"
                        data[3] = (
                            str(line.contract_id.date_end)[-2:]
                            + str(line.contract_id.date_end)[5:7]
                            + str(line.contract_id.date_end)[:4]
                        )
                        data[4] = " " * 8
                        data[5] = " " * 2
                        data[6] = " " * 7

                        lines += "".join(str(d) for d in data) + "\n"

                    self.txt_file = base64.b64encode(lines.encode())
                    return {
                        "type": "ir.actions.act_url",
                        "url": "/web/content/hr.payroll.sua.reports/"
                        + "%s/txt_file/%s?download=true" % (self.id, "movt.txt"),
                        "target": "self",
                    }
                if sua.movt_type == "07":
                    for line in self.line_ids:
                        date = sorted(
                            line.name.contract_id.salary_history_ids,
                            key=lambda x: x.date_applied,
                            reverse=True,
                        )[0]
                        data = [""] * 7
                        data[0] = line.name.employer_register.name
                        data[1] = line.name.ssnid.zfill(11)
                        data[2] = "07"
                        data[3] = (
                            str(date.date_applied)[-2:]
                            + str(date.date_applied)[5:7]
                            + str(date.date_applied)[:4]
                        )
                        data[4] = " " * 8
                        data[5] = " " * 2
                        data[6] = (
                            format(line.name.contract_id.sdi, ".2f")
                            .replace(".", "")
                            .zfill(7)
                        )

                        lines += "".join(str(d) for d in data) + "\n"

                    self.txt_file = base64.b64encode(lines.encode())
                    return {
                        "type": "ir.actions.act_url",
                        "url": "/web/content/hr.payroll.sua.reports/"
                        + "%s/txt_file/%s?download=true" % (self.id, "movt.txt"),
                        "target": "self",
                    }
                if sua.movt_type == "08":
                    for line in self.line_ids:
                        data = [""] * 7
                        data = [""] * 7
                        data[0] = line.name.employer_register.name
                        data[1] = line.name.ssnid.zfill(11)
                        data[2] = "08"
                        data[3] = (
                            str(line.contract_id.date_start.strftime("%d"))
                            + str(line.contract_id.date_start.strftime("%m"))
                            + str(line.contract_id.date_start.strftime("%Y"))
                        )
                        data[4] = " " * 8
                        data[5] = " " * 2
                        data[6] = (
                            format(line.name.contract_id.sdi, ".2f")
                            .replace(".", "")
                            .zfill(7)
                        )

                        lines += "".join(str(d) for d in data) + "\n"

                    self.txt_file = base64.b64encode(lines.encode())
                    return {
                        "type": "ir.actions.act_url",
                        "url": "/web/content/hr.payroll.sua.reports/"
                        + "%s/txt_file/%s?download=true" % (self.id, "movt.txt"),
                        "target": "self",
                    }
                if sua.movt_type in ["11", "12"]:
                    _logger.info("SUA to TXT -->>  11 o 12")
                    for line in self.line_ids:
                        employer_register = line.name.employer_register.name
                        ssnid = line.name.ssnid

                        data = [""] * 7
                        data[0] = employer_register
                        data[1] = ssnid.zfill(11)
                        data[2] = sua.movt_type
                        data[3] = line.date.strftime("%d%m%Y")
                        if isinstance(line.timeoff_id.disability_folio, str):
                            data[4] = line.timeoff_id.disability_folio[:8]
                        else:
                            data[4] = " " * 8
                        data[5] = str(
                            int(line.timeoff_id.number_of_days_display)
                        ).zfill(2)
                        data[6] = " " * 7

                        lines += "".join(str(d) for d in data) + "\n"

                    self.txt_file = base64.b64encode(lines.encode())
                    return {
                        "type": "ir.actions.act_url",
                        "url": "/web/content/hr.payroll.sua.reports/"
                        + "%s/txt_file/%s?download=true" % (self.id, "movt.txt"),
                        "target": "self",
                    }


class HrPayrollSUAReportsLine(models.Model):
    _name = "hr.payroll.sua.reports.line"
    _description = "Payroll SUA Reports Line"

    line_id = fields.Many2one(
        "hr.payroll.sua.reports", required=True, ondelete="cascade"
    )
    name = fields.Many2one("hr.employee")
    date = fields.Date()
    contract_id = fields.Many2one("hr.contract")
    ssnid = fields.Char(string="NSS")
    amount = fields.Float()
    timeoff_id = fields.Many2one("hr.leave")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("paid", "Paid"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )
    company_id = fields.Many2one("res.company")
