import base64

from odoo import fields, models


class HrPayrollDispersion(models.TransientModel):
    _name = "hr.payroll.dispersion"
    _description = "Generate Payroll Dispersion banks"

    name = fields.Char()
    bank_id = fields.Many2one("res.bank")
    transfer_date = fields.Date()
    payslip_run_id = fields.Many2one("hr.payslip.run")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    partner_bank_id = fields.Many2one("res.partner.bank")
    account_number = fields.Char()
    bank_branch = fields.Char()
    contract_number = fields.Char()
    batch_number = fields.Char()
    txt_file = fields.Binary("txt file")

    def compute_sheet(self):
        self.ensure_one()
        n = 1
        data = ""
        lines = ""

        for payslip_id in self.payslip_run_id.slip_ids:
            if (
                not payslip_id.employee_id.address_home_id
                or not payslip_id.employee_id.address_home_id.bank_ids
                or not payslip_id.employee_id.address_home_id.bank_ids.filtered(
                    lambda acc: acc.bank_id == self.bank_id
                )
            ):
                continue
            acc_number = payslip_id.employee_id.address_home_id.bank_ids.filtered(
                lambda acc: acc.bank_id == self.bank_id
            )[0].acc_number
            data = [""] * 9
            data[0] = (str(n)).rjust(10, "0")
            data[1] = " " * 10
            data[2] = "%012d" % int(acc_number)
            data[3] = " " * 10
            data[4] = "%010d" % payslip_id.amount_total
            data[5] = " " * 10
            data[6] = (
                (
                    payslip_id.employee_id.lastname
                    + " "
                    + payslip_id.employee_id.second_lastname
                    + " "
                    + payslip_id.employee_id.firstname
                ).upper()
            ).ljust(20, " ")
            data[7] = " " * 10
            data[8] = "001001"

            lines += "".join(str(d) for d in data) + "\n"
            n += 1
        if lines != "":
            self.txt_file = base64.b64encode(lines.encode())
            return {
                "type": "ir.actions.act_url",
                "url": "/web/content/hr.payroll.dispersion/%s/txt_file/%s?download=true"
                % (self.id, self.bank_id.name + ".txt"),
                "target": "self",
            }
