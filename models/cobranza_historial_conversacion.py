# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np

class CobranzaHistorialConversacion(models.Model):
	_name = 'cobranza.historial.conversacion'

	_order = 'id desc'
	partner_id = fields.Many2one('res.partner')
	numero = fields.Char('Numero')
	respondio = fields.Selection([
		('titular', 'Titular'), ('familiar', 'Familiar'), 
		('contacto', 'Contacto'), ('amigo', 'Amigo/a'), 
		('empleador', 'Empleador'), ('vecino', 'Vecino'),
		('otro', 'Otro')], "Respondio")
	conversacion = fields.Char('Conversacion')
	estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Resultado')
	es_promesa_de_pago = fields.Boolean("Es promesa de pago?")
	fecha_promesa_de_pago = fields.Date('Fecha promesa de pago')
	proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	proxima_accion_fecha = fields.Datetime('Fecha proxima accion')
	saldo_mora = fields.Float('Saldo en mora', digits=(16, 2), readonly=True)
	registro_editable = fields.Boolean("Registro editable", compute='_compte_registro_editable')
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
			rec.update({
				'partner_id': deudor_id.id,
				'registro_editable': True,
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
	@api.onchange('proxima_accion_id')
	def _onchange_proxima_accion_id(self):
		if self.proxima_accion_id.intervalo_cantidad > 0:
			if self.proxima_accion_id.invervalo_unidad == 'minutos':
				self.proxima_accion_fecha = datetime.now() + timedelta(minutes=self.proxima_accion_id.intervalo_cantidad)
			elif self.proxima_accion_id.invervalo_unidad == 'horas':
				self.proxima_accion_fecha = datetime.now() + timedelta(hours=self.proxima_accion_id.intervalo_cantidad)
			elif self.proxima_accion_id.invervalo_unidad == 'dias':
				self.proxima_accion_fecha = datetime.now() + timedelta(days=self.proxima_accion_id.intervalo_cantidad)

	@api.one
	def _compte_registro_editable(self):
		registro_editable = True
		if self.create_date:
			now = datetime.now()
			create_date = datetime.strptime(self.create_date, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=1)
			if now > create_date:
				registro_editable = False
		self.registro_editable = registro_editable

class CobranzaHistorialConversacionEstado(models.Model):
	_name = 'cobranza.historial.conversacion.estado'

	_oreder = 'id desc'
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
