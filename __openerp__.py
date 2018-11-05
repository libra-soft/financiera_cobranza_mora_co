# -*- coding: utf-8 -*-
{
    'name': "Financiera - Cobranza Mora",

    'summary': """
        Gestion de cobranza - historial de conversasion con el deudor.""",

    'description': """
        Gestion de cobranza - historial de conversasion con el deudor.
    """,

    'author': "Librasoft",
    'website': "https://www.libra-soft.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'finance',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'financiera_prestamos'],

    # always loaded
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'data/ir_cron.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}