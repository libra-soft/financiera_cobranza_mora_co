# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np


class ExtendsResPartner(models.Model):
	_name = 'res.partner'
	_inherit = 'res.partner'

	cuota_mora_ids = fields.One2many('financiera.prestamo.cuota', 'partner_cuota_mora_id', 'Cuotas en mora')
	saldo_mora = fields.Float('Saldo en mora', digits=(16, 2))
	cobranza_historial_conversacion_ids = fields.One2many('cobranza.historial.conversacion', 'partner_id', 'Historial de conversacion')

	@api.model
	def cron_cuotas_mora(self):
		cr = self.env.cr
		uid = self.env.uid
		partner_obj = self.pool.get('res.partner')
		partner_ids = partner_obj.search(cr, uid, [])
		for _id in partner_ids:
			partner_id = partner_obj.browse(cr, uid, _id)
			partner_id.compute_cuotas_mora()

	@api.one
	def compute_cuotas_mora(self):
		cr = self.env.cr
		uid = self.env.uid
		self.cuota_mora_ids = None
		cuota_obj = self.pool.get('financiera.prestamo.cuota')
		cuota_ids = cuota_obj.search(cr, uid, [
			('cliente_id', '=', self.id),
			('state_mora', '!=', 'normal'),
			('state', 'in', ('activa', 'facturado')),
		])
		self.cuota_mora_ids = cuota_ids
		self._saldo_mora()


	@api.one
	def _saldo_mora(self):
		saldo = 0
		for cuota_id in self.cuota_mora_ids:
			saldo += cuota_id.saldo
		self.saldo_mora = saldo

class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	partner_cuota_mora_id = fields.Many2one('res.partner', "Cuota en mora")

	@api.one
	def confirmar_cobrar_cuota(self):
		rec = super(ExtendsFinancieraPrestamoCuota, self).confirmar_cobrar_cuota()
		self.cliente_id.compute_cuotas_mora()

class CobranzaHistorialConversacion(models.Model):
	_name = 'cobranza.historial.conversacion'

	_order = 'id desc'
	partner_id = fields.Many2one('res.partner')
	conversacion = fields.Char('Conversacion')
	estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Estado')
	proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	proxima_accion_fecha = fields.Datetime('Fecha')
	saldo_mora = fields.Float('Saldo en mora', digits=(16, 2), readonly=True)

	@api.model
	def create(self, values):
		rec = super(CobranzaHistorialConversacion, self).create(values)
		rec.update({
			'saldo_mora': rec.partner_id.saldo_mora,
		})
		return rec

class CobranzaHistorialConversacionEstado(models.Model):
	_name = 'cobranza.historial.conversacion.estado'

	name = fields.Char('Estado')


class CobranzaHistorialConversacionAccion(models.Model):
	_name = 'cobranza.historial.conversacion.accion'

	name = fields.Char('Accion')

class SessionCobranza(models.Model):
	_name = 'cobranza.session'

	fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	current_user = fields.Many2one('res.users','Current User', default=lambda self: self.env.user)
	state = fields.Selection([('preparado', 'Preparado'), ('proceso', 'En proceso'), ('finalizado', 'Finalizado')], string='Estado', readonly=True, default='preparado')
	# Control time
	process_time = fields.Datetime('Hora de proceso')
	process_minutes = fields.Float('Minutos en proceso', compute='_compute_process_minutes')
	process_time_finish = fields.Datetime('Hora finalizacion de proceso')


	@api.one
	def _compute_process_minutes(self):
		datetimeFormat = '%Y-%m-%d %H:%M:%S'
		date_start = None
		date_finish = datetime.now()
		if self.process_time_finish:
			date_finish = datetime.strptime(self.process_time_finish,datetimeFormat)
		if self.process_time:
			date_start = self.process_time
			start = datetime.strptime(date_start, datetimeFormat)
			finish = date_finish
			result = finish - start
			minutos = result.seconds / 60
			self.process_minutes = minutos
		else:
			self.process_minutes = 0
