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

