{
    'name': 'Employee Net Pay Report',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Generate Excel report of employee details',
    'depends': ['base', 'hr', 'hr_payroll'],
    'author' : 'James Otieno',
    'data': [
    'security/ir.model.access.csv',
    'wizard/hr_payslip_report_wizard.xml',
    'views/hr_payslip_report_menu.xml',
    ],
    'installable': True,
}
