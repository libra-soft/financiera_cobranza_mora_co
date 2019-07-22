# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np


GLOBAL_VALUE_ACCIONES_SUGERIDAS = [('accion1', '		'), ('accion2', '		'), ('accion3', '		')]

class CobranzaHistorialConversacion(models.Model):
	_name = 'cobranza.historial.conversacion'

	_order = 'id desc'
	partner_id = fields.Many2one('res.partner')
	conversacion = fields.Char('Conversacion')
	estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Resultado')
	proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	proxima_accion_fecha = fields.Datetime('Fecha')
	saldo_mora = fields.Float('Saldo en mora', digits=(16, 2), readonly=True)
	# Posibles acciones siguientes
	acciones_sugeridas = fields.Selection(GLOBAL_VALUE_ACCIONES_SUGERIDAS, string='Acciones sugeridas')
	accion_siguiente_1 = fields.Many2one('cobranza.historial.conversacion.accion')
	char_accion_siguiente_1 = fields.Char()
	accion_siguiente_2 = fields.Many2one('cobranza.historial.conversacion.accion')
	char_accion_siguiente_2 = fields.Char()
	accion_siguiente_3 = fields.Many2one('cobranza.historial.conversacion.accion')
	char_accion_siguiente_3 = fields.Char()
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('cobranza.historial.conversacion'))

	@api.model
	def default_get(self, fields):
		rec = super(CobranzaHistorialConversacion, self).default_get(fields)
		context = dict(self._context or {})
		active_id = context.get('active_id')
		cr = self.env.cr
		uid = self.env.uid
		current_user = self.env['res.users'].browse(uid)
		deudor_ids = self.pool.get('res.partner').search(cr, uid, [
			('company_id', '=', current_user.company_id.id),
			('id', '=', active_id)
		])
		if len(deudor_ids) > 0:
			deudor_id = self.env['res.partner'].browse(active_id)
			accion_siguiente_1 = None
			char_accion_siguiente_1 = None
			accion_siguiente_2 = None
			char_accion_siguiente_2 = None
			accion_siguiente_3 = None
			char_accion_siguiente_3 = None
			if len(deudor_id) > 0 and len(deudor_id.cobranza_historial_conversacion_ids) > 0:
				chca_id = deudor_id.cobranza_historial_conversacion_ids[0].proxima_accion_id
				if len(chca_id) > 0 and len(chca_id.accion_siguiente_1) > 0:
					accion_siguiente_1 = chca_id.accion_siguiente_1.id
					char_accion_siguiente_1 = chca_id.accion_siguiente_1.name
				if len(chca_id) > 0 and len(chca_id.accion_siguiente_2) > 0:
					accion_siguiente_2 = chca_id.accion_siguiente_2.id
					char_accion_siguiente_2 = chca_id.accion_siguiente_2.name
				if len(chca_id) > 0 and len(chca_id.accion_siguiente_3) > 0:
					accion_siguiente_3 = chca_id.accion_siguiente_3.id
					char_accion_siguiente_3 = chca_id.accion_siguiente_3.name
			rec.update({
				'partner_id': deudor_id.id,
				'accion_siguiente_1': accion_siguiente_1,
				'char_accion_siguiente_1': char_accion_siguiente_1,
				'accion_siguiente_2': accion_siguiente_2,
				'char_accion_siguiente_2': char_accion_siguiente_2,
				'accion_siguiente_3': accion_siguiente_3,
				'char_accion_siguiente_3': char_accion_siguiente_3,
			})
		return rec

	@api.model
	def create(self, values):
		rec = super(CobranzaHistorialConversacion, self).create(values)
		rec.update({
			'saldo_mora': rec.partner_id.saldo_mora,
		})
		rec.partner_id.cobranza_estado_id = values['estado_id']
		rec.partner_id.cobranza_proxima_accion_id = values['proxima_accion_id']
		rec.partner_id.cobranza_proxima_accion_fecha = values['proxima_accion_fecha']
		rec.partner_id.cobranza_disponible = True
		return rec


	@api.one
	@api.onchange('acciones_sugeridas')
	def _onchange_acciones_sugeridas(self):
		if self.acciones_sugeridas == 'accion1':
			self.proxima_accion_id = self.accion_siguiente_1
		elif self.acciones_sugeridas == 'accion2':
			self.proxima_accion_id = self.accion_siguiente_2
		elif self.acciones_sugeridas == 'accion3':
			self.proxima_accion_id = self.accion_siguiente_3



	@api.one
	@api.onchange('proxima_accion_id')
	def _onchange_proxima_accion_id(self):
		if self.proxima_accion_id.intervalo_cantidad > 0:
			if self.proxima_accion_id.invervalo_unidad == 'minutos':
				self.proxima_accion_fecha = datetime.now() + timedelta(minutes=self.proxima_accion_id.intervalo_cantidad)
			elif self.proxima_accion_id.invervalo_unidad == 'horas':
				self.proxima_accion_fecha = datetime.now() + timedelta(hours=self.proxima_accion_id.intervalo_cantidad)
			elif self.proxima_accion_id.invervalo_unidad == 'dias':
				self.proxima_accion_fecha = datetime.now() + timedelta(days=self.proxima_accion_id.intervalo_cantidad)



class CobranzaHistorialConversacionEstado(models.Model):
	_name = 'cobranza.historial.conversacion.estado'

	name = fields.Char('Estado')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('cobranza.historial.conversacion.estado'))


class CobranzaHistorialConversacionAccion(models.Model):
	_name = 'cobranza.historial.conversacion.accion'

	name = fields.Char('Accion')
	invervalo_unidad = fields.Selection([('minutos', 'Minutos'), ('horas', 'Horas'), ('dias', 'Dias')], string='Unidad de invervalo', default='minutos')
	intervalo_cantidad = fields.Integer('Cantidad de intervalos')
	accion_siguiente_1 = fields.Many2one('cobranza.historial.conversacion.accion')
	accion_siguiente_2 = fields.Many2one('cobranza.historial.conversacion.accion')
	accion_siguiente_3 = fields.Many2one('cobranza.historial.conversacion.accion')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('cobranza.historial.conversacion.accion'))
