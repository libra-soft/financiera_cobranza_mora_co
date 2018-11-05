# -*- coding: utf-8 -*-
from openerp import http

# class FinancieraCobranzaMora(http.Controller):
#     @http.route('/financiera_cobranza_mora/financiera_cobranza_mora/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/financiera_cobranza_mora/financiera_cobranza_mora/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('financiera_cobranza_mora.listing', {
#             'root': '/financiera_cobranza_mora/financiera_cobranza_mora',
#             'objects': http.request.env['financiera_cobranza_mora.financiera_cobranza_mora'].search([]),
#         })

#     @http.route('/financiera_cobranza_mora/financiera_cobranza_mora/objects/<model("financiera_cobranza_mora.financiera_cobranza_mora"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('financiera_cobranza_mora.object', {
#             'object': obj
#         })