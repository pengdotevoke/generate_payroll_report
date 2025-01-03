from odoo import models, fields, api
import base64
import io
import xlsxwriter
from datetime import datetime 
from dateutil.relativedelta import relativedelta

class HrPayslipReportWizard(models.TransientModel):
    _name = 'hr.payslip.report.wizard'
    _description = 'Generate Excel Report for Payslip Details'

    report_file_net_pay = fields.Binary("Net Pay Report", readonly=True)
    report_file_net_pay_name = fields.Char("File Name", default="Net_Pay_Report.xlsx")
    report_file_nssf = fields.Binary("NSSF Report", readonly=True)
    report_file_nssf_name = fields.Char("File Name", default="NSSF_Report.xlsx")
    report_file_shif = fields.Binary("SHIF Report", readonly=True)
    report_file_shif_name = fields.Char("File Name", default="SHIF_Report.xlsx")
    report_file_ahl = fields.Binary("AHL Report", readonly=True)
    report_file_ahl_name = fields.Char("File Name", default="AHL_Report.xlsx")
    report_file_kra_pin = fields.Binary("PAYE Report", readonly=True)
    report_file_kra_pin_name = fields.Char("File Name", default="PAYE_Report.xlsx")

    month = fields.Selection(
        [(str(i), datetime(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string="Month",
        required=True,
        default=str(datetime.today().month)
    )
    year = fields.Selection(
        [(str(i), str(i)) for i in range(2024, datetime.today().year + 1)],
        string="Year",
        required=True,
        default=str(datetime.today().year)
    )

    date_from = fields.Date(string="Date From", readonly=True)
    date_to = fields.Date(string="Date To", readonly=True)

    @api.onchange('month', 'year')
    def _compute_dates(self):
        if self.month and self.year:
            self.date_from = datetime(int(self.year), int(self.month), 1)
            self.date_to = (self.date_from + relativedelta(months=1) - relativedelta(days=1))

    def generate_report(self):
        # Compute date range from user input
        self._compute_dates()

        def create_workbook(filename, worksheet_title, headers, rows):
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet(worksheet_title)

            company_name = self.env.company.name
            first_date = self.date_from.strftime('%Y-%m-%d') if self.date_from else ''
            last_date = self.date_to.strftime('%Y-%m-%d') if self.date_to else ''
            month_name = datetime.strptime(self.month, '%m').strftime('%B')

            worksheet.write(0, 0, f"{company_name}")
            worksheet.write(1, 0, f"Date From: {first_date}")
            worksheet.write(2, 0, f"Date To: {last_date}")
            worksheet.write(3, 0, f"Payroll Summary: {worksheet_title} report for {month_name} {self.year}")

            for col_num, header in enumerate(headers):
                worksheet.write(5, col_num, header)

            row = 6
            for data_row in rows:
                for col_num, cell_data in enumerate(data_row):
                    worksheet.write(row, col_num, cell_data)
                row += 1

            workbook.close()
            output.seek(0)
            return base64.b64encode(output.read())

        payslips = self.env['hr.payslip'].search([
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to)
        ])

        # Net Pay Report
        headers_net_pay = ['Employee Name', 'Bank Name', 'Bank Branch', 'Net Pay']
        rows_net_pay = [[p.employee_id.name, 
                         p.employee_id.bank_account_id.bank_name if p.employee_id.bank_account_id else '',
                         p.employee_id.bank_account_id.bank_bic if p.employee_id.bank_account_id else '',
                         p.net_wage] for p in payslips]
        self.report_file_net_pay = create_workbook("Net_Pay_Report.xlsx", "Payslip Report", headers_net_pay, rows_net_pay)

        # NSSF Report
        headers_nssf = ['Payroll Number', 'Surname', 'Other Names',  'ID Number', 'KRA PIN', 'NSSF Number', 'Gross pay', 'Voluntary']
        rows_nssf = [[ 
                      p.employee_id.registration_number or '',
                      p.employee_id.name.split()[-1]or '',
                      ' '.join(p.employee_id.name.split()[:-1]) if len(p.employee_id.name.split()) > 1 else p.employee_id.name or '',
                      p.employee_id.identification_id or '',
                      p.employee_id.l10n_ke_kra_pin or '',
                      p.employee_id.l10n_ke_nssf_number or '',
                      p.gross_wage or ''] for p in payslips]
        self.report_file_nssf = create_workbook("NSSF_Report.xlsx", "NSSF Report", headers_nssf, rows_nssf)

        # SHIF Report
        headers_shif = ['Payroll Number', 'First Name', 'Last Name', 'ID Number','KRA PIN', 'SHIF Number', 'AMOUNT', 'PHONE']
        rows_shif = [
            [
                p.employee_id.registration_number or '',
                p.employee_id.name.split()[0] or '', 
                p.employee_id.name.split()[1] or '',
                p.employee_id.identification_id or '',
                p.employee_id.l10n_ke_kra_pin or '',
                p.employee_id.l10n_ke_nhif_number or '',
                p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'SHA').amount or 0,
                p.employee_id.work_phone or '',
            ]
            for p in payslips
        ]
        self.report_file_shif = create_workbook("SHIF_Report.xlsx", "SHIF Report", headers_shif, rows_shif)


       # KRA PIN Filtered Report
        target_kra_pins = {
            'A011167362P': 'Primary Employee',
            'A006222056J': 'Secondary Employee'
        }
        headers_kra_pin = []
        rows_kra_pin = [
            [p.employee_id.l10n_ke_kra_pin, 
             p.employee_id.name, 
             target_kra_pins.get(p.employee_id.l10n_ke_kra_pin, ''), 
             p.net_wage, 
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'Taxed_House_Allowance').amount or 0, 
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'TAXED_BONUS').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'SALARY ADVANCE').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'Taxed_Acting_Allowance').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'Taxed_Leave_Travelling_Allowance').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'Lump_Sum_Pay').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'SERVICE_CHARGE').amount or 0, 
             '',0,0,'','',0,
             'Benefit not Given',
             '','','','','','',
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'NSSF_AMOUNT').amount or 0,
             '',0,0,'','','','',
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'PERS_RELIEF').amount or 0,
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'INSURANCE_RELIEF').amount or 0,
             '',
             p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'PAYE').amount or 0,
             ]
            for p in payslips
        ]

        self.report_file_kra_pin = create_workbook("PAYE_Report.xlsx", "PAYE Report", headers_kra_pin, rows_kra_pin)


        # AHL Report. Modify to remove AHL in line with new rules
        headers_ahl = ['ID NO', 'NAME', 'KRA PIN', 'GROSS WAGE', 'AHL SELF', 'AHL EMPLOYER']
        rows_ahl = [
            [
                p.employee_id.identification_id,
                p.employee_id.name,
                p.employee_id.l10n_ke_kra_pin,
                p.gross_wage,
                p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'AHL_AMOUNT').amount or 0,
                p.line_ids.filtered(lambda line: line.salary_rule_id.code == 'AHL_AMOUNT_EMP').amount or 0
            ]
            for p in payslips
        ]
        self.report_file_ahl = create_workbook("AHL_Report.xlsx", "AHL Report", headers_ahl, rows_ahl)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }
