# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np

class CobranzaLista(models.Model):
	_name = 'cobranza.lista'
	
	# fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	# current_user = fields.Many2one('res.users','Current User', default=lambda self: self.env.user)
	# state = fields.Selection([('borrador', 'Borrador'), ('proceso', 'En proceso'), ('finalizada', 'Finalizada')], string='Estado', readonly=True, default='borrador')
	deudor_ids = fields.One2many('res.partner', 'cobranza_lista_id', "Deudores")
	indice_ultimo_deudor = fields.Integer('Indice ultimo deudor', default=0)
	cantidad_deudores = fields.Integer('Cantidad de deudores', compute='_compute_cantidad_deudores')

	@api.one
	def _compute_cantidad_deudores(self):
		self.cantidad_deudores = len(self.deudor_ids)

	@api.one
	def proximo_deudor(self):
		if self.indice_ultimo_deudor < len(self.deudor_ids)
		self.deudor_ids[self.indice_ultimo_deudor]

class ExtendsResPartner(models.Model):
	_name = 'res.partner'
	_inherit = 'res.partner'

	cobranza_lista_id = fields.Many2one('cobranza.lista', 'Lista')
	disponible_cobranza = fields.Boolean('Disponible', default=True)
