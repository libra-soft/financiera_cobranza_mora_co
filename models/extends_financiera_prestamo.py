# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from datetime import datetime, timedelta, date
from openerp.exceptions import UserError, ValidationError

class ExtendsFinancieraPrestamo(models.Model):
	_inherit = 'financiera.prestamo' 
	_name = 'financiera.prestamo'

	suscripto_debito_cbu = fields.Boolean('Debito por CBU', related='partner_id.suscripto_debito_cbu')
	no_debitar_cbu = fields.Boolean('No debitar por CBU')

	# @api.multi
	# def cobranza_actualizar_estado_cupon(self):
	# 	print("cobranza_actualizar_estado_cupon")
	# 	pagos_360_id = self.company_id.pagos_360_id
	# 	if self.state in ('activa', 'judicial', 'incobrable'):
	# 		solicitud_pago = self.pagos_360_obtener_solicitud_pago()
	# 		self.pagos_360_solicitud_state = solicitud_pago['state']
	# 		self.pagos_360_solicitud_id_origen_pago = solicitud_pago['id']
	# 		if self.state in ('activa', 'judicial', 'incobrable') and solicitud_pago['state'] == 'paid':
	# 			request_result = solicitud_pago['request_result'][0]
	# 			superuser_id = self.sudo().pool.get('res.users').browse(self.env.cr, self.env.uid, 1)
	# 			superuser_id.sudo().company_id = self.company_id.id
	# 			journal_id = pagos_360_id.journal_id
	# 			factura_electronica = pagos_360_id.factura_electronica
	# 			payment_date = request_result['paid_at']
	# 			amount = request_result['amount']
	# 			invoice_date = datetime.now()
	# 			self.pagos_360_cobrar_y_facturar(payment_date, journal_id, factura_electronica, amount, invoice_date)
	# 			self.pagos_360_solicitud_state = 'paid'
	# 			pagos_360_id.actualizar_saldo()
	# 	return {'type': 'ir.actions.do_nothing'}


	# @api.multi
	# def cobranza_action_cupon_sent(self):
	# 	""" Open a window to compose an email, with the edi cupon template
	# 		message loaded by default
	# 	"""
	# 	self.ensure_one()
	# 	template = self.env.ref('financiera_pagos_360.email_template_edi_cupon', False)
	# 	compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
	# 	ctx = dict(
	# 		default_model='financiera.prestamo.cuota',
	# 		default_res_id=self.id,
	# 		default_use_template=bool(template),
	# 		default_template_id=template and template.id or False,
	# 		default_composition_mode='comment',
	# 		sub_action='cupon_sent',
	# 		# mark_invoice_as_sent=True,
	# 	)
	# 	return {
	# 		'name': 'Envio cupon de pago',
	# 		'type': 'ir.actions.act_window',
	# 		'view_type': 'form',
	# 		'view_mode': 'form',
	# 		'res_model': 'mail.compose.message',
	# 		'views': [(compose_form.id, 'form')],
	# 		'view_id': compose_form.id,
	# 		'target': 'new',
	# 		'context': ctx,
	# 	}
