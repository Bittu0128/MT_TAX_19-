# -*- coding: utf-8 -*-
#
#################################################################################
# Author      : Weblytic Labs Pvt. Ltd. (<https://store.weblyticlabs.com/>)
# Copyright(c): 2023-Present Weblytic Labs Pvt. Ltd.
# All Rights Reserved.
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
##################################################################################

{
    'name': 'Mergin Tax',
    'version': '18.0.1.0.0',
    'sequence': -1,
    'summary': """Website Mergin Tax""",
    'description': """Website Mergin Tax""",
    'category': 'eCommerce',
    'author': 'Weblytic Labs',
    'company': 'Weblytic Labs',
    'website': "https://store.weblyticlabs.com",
    'depends': ['base', 'point_of_sale', 'web', 'website', 'account', 'website_sale', 'sale_management'],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': True,
    'data': [
        'data/mergin_tax_data.xml',
        'views/sale_order_line.xml',
        'views/taxes_view.xml',
        'views/product_template_inherit.xml',
        'views/inherit_report_invoice.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
        ],
    }
}
