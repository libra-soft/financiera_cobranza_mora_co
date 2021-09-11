# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np


class ExtendsResPartner(models.Model):
	_name = 'res.partner'
	_inherit = 'res.partner'

	cuota_mora_ids = fields.One2many('financiera.prestamo.cuota', 'partner_cuota_mora_id', 'Cuotas en mora')
	cuota_mora_numero = fields.Char('Cuota a cobrar numero')
	cuota_mora_monto = fields.Float('Cuota a cobrar monto', digits=(16, 2))
	pagos_360_checkout_url = fields.Char('Pagos360 - Url de pago online', compute='_compute_link_pagos_360')
	pagos_360_pdf_url = fields.Char('Pagos360 - Url de cupon de pago en pdf', compute='_compute_link_pagos_360')
	referido_1_nombre = fields.Char('Referido 1')
	referido_1_celular = fields.Char('Referido 1 celular')
	referido_2_nombre = fields.Char('Referido 2')
	referido_2_celular = fields.Char('Referido 2 celular')
	saldo_mora = fields.Float('Deuda en mora', digits=(16, 2))
	saldo_total = fields.Float('Deuda total', digits=(16, 2))
	cobranza_historial_conversacion_ids = fields.One2many('cobranza.historial.conversacion', 'partner_id', 'Historial de conversacion')
	cobranza_disponible = fields.Boolean('Disponible', default=True)
	# Estado actual
	cobranza_estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Estado')
	cobranza_proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	cobranza_proxima_accion_fecha = fields.Datetime('Fecha proxima accion')
	# Estado de mora
	mora_id = fields.Many2one('res.partner.mora', 'Segmento')
	# Notificaiones
	notificacion_ids = fields.One2many('financiera.cobranza.notificacion', 'partner_id', 'Notificaciones')
	# Estudio de cobranza externa
	cobranza_externa_id = fields.Many2one('financiera.cobranza.externa', 'Cobranza externa')

	@api.one
	def compute_cuotas_mora(self):
		self.cuota_mora_ids = None
		cuota_obj = self.pool.get('financiera.prestamo.cuota')
		cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
			('partner_id', '=', self.id),
			('state_mora', 'not in', ('preventiva', 'normal')),
			('state', 'in', ('activa', 'judicial', 'incobrable')),
		])
		self.cuota_mora_ids = cuota_ids
		self._saldo_mora()
		self.compute_cuota_mora()
		self.compute_referidos()

	@api.one
	def _saldo_mora(self):
		saldo = 0
		for cuota_id in self.cuota_mora_ids:
			saldo += cuota_id.saldo
		self.saldo_mora = saldo

	@api.one
	def compute_cuota_mora(self):
		if len(self.cuota_mora_ids) > 0:
			self.write({
				'cuota_mora_numero': self.cuota_mora_ids[0].numero_cuota,
				'cuota_mora_monto': self.cuota_mora_ids[0].saldo,
			})
	
	@api.one
	def _compute_link_pagos_360(self):
		if len(self.cuota_mora_ids) > 0:
			self.pagos_360_checkout_url = self.cuota_mora_ids[0].pagos_360_checkout_url
			self.pagos_360_pdf_url = self.cuota_mora_ids[0].pagos_360_pdf_url

	@api.one
	def compute_referidos(self):
		len_contactos = len(self.contacto_ids)
		values = {}
		if len_contactos > 1:
			values['referido_2_nombre'] = self.contacto_ids[1].name
			values['referido_2_celular'] = self.contacto_ids[1].movil
		if len_contactos > 0:
			values['referido_1_nombre'] = self.contacto_ids[0].name
			values['referido_1_celular'] = self.contacto_ids[0].movil
			self.write(values)

	@api.model
	def cobranza_siguiente_deudor(self):
		cr = self.env.cr
		uid = self.env.uid
		current_user = self.env['res.users'].browse(uid)
		ret_deudor_id = None
		deudor_obj = self.pool.get('res.partner')
		deudor_primera_accion_ids = deudor_obj.search(cr, uid, [
			('saldo_mora', '>', 0),
			('cobranza_disponible', '=', True),
			('cobranza_proxima_accion_fecha', '=', False),
			('cobranza_externa_id', '=', False),
			('company_id', '=', current_user.company_id.id),
		])
		if len(deudor_primera_accion_ids) > 0:
			ret_deudor_id = deudor_obj.browse(cr, uid, deudor_primera_accion_ids[0])
			ret_deudor_id.cobranza_disponible = False
		else:
			date_now = datetime.now()
			deudor_ids = deudor_obj.search(cr, uid, [
				('saldo_mora', '>', 0),
				('cobranza_disponible', '=', True),
				('cobranza_externa_id', '=', False),
				('company_id', '=', current_user.company_id.id),
				('cobranza_proxima_accion_fecha', '<=', str(date_now))
			], order='cobranza_proxima_accion_fecha asc', limit=1)
			if len(deudor_ids) > 0:
				partner_id = deudor_obj.browse(cr, uid, deudor_ids[0])
				ret_deudor_id = partner_id
				ret_deudor_id.cobranza_disponible = False
		return ret_deudor_id

	@api.multi
	def carta_documento_report(self):
		self.ensure_one()
		if len(self.company_id.cobranza_config_id) > 0:
			return self.env['report'].get_action(self, "financiera_cobranza_mora.carta_documento_report_view")
		else:
			raise UserError("Modulo cobranza no esta contartado.")

class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	partner_cuota_mora_id = fields.Many2one('res.partner', "Cuota en mora")
