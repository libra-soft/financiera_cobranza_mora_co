# -*- coding: utf-8 -*-

from openerp import models, fields

class FinancieraCobranzaNotificacion(models.Model):
	_name = 'financiera.cobranza.notificacion'

	_order = 'fecha desc'
	partner_id = fields.Many2one('res.partner', 'Cliente')
	fecha = fields.Datetime("Fecha")
	item_id = fields.Many2one('financiera.cobranza.notificacion.item', "Nombre")
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.notificacion'))

class FinancieraCobranzaNotificacionItem(models.Model):
	_name = 'financiera.cobranza.notificacion.item'

	name = fields.Char("Nombre")
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.notificacion.item'))

