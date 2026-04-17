# -*- coding: utf-8 -*-
# from odoo import http


# class MsuHolzonnOperations(http.Controller):
#     @http.route('/msu_holzonn_operations/msu_holzonn_operations', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/msu_holzonn_operations/msu_holzonn_operations/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('msu_holzonn_operations.listing', {
#             'root': '/msu_holzonn_operations/msu_holzonn_operations',
#             'objects': http.request.env['msu_holzonn_operations.msu_holzonn_operations'].search([]),
#         })

#     @http.route('/msu_holzonn_operations/msu_holzonn_operations/objects/<model("msu_holzonn_operations.msu_holzonn_operations"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('msu_holzonn_operations.object', {
#             'object': obj
#         })

