# -*- coding: utf-8 -*-
{
    'name': "msu_holzonn_operations",
    'summary': "Holzinn Homes",
    'author': "Muhammad Sana Ullah",
    'website': "https://synavos.com/",
    'category': 'Customization',
    'version': '0.1',
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'purchase', 'holzinhome_operations', 'web'],
    
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/holzinn_oper_views.xml',
        'views/work_order_views.xml',
        'views/account_move_views.xml',
        'views/stock_quant_views.xml',
        'views/idico_form_view_ext.xml',
        'views/sale_order_menus.xml',
        'views/res_users_views.xml',
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'msu_holzinn_operations/static/src/css/sticky_header.css',
            'msu_holzinn_operations/static/src/js/idle_timeout.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
