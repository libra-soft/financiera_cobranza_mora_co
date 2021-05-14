# -*- coding: utf-8 -*-

from openerp import models, fields, api

class ResPartnerMora(models.Model):
	_name = 'res.partner.mora'

	_order = 'orden asc'
	name = fields.Char('Nombre')
	orden = fields.Integer("Orden")
	config_id = fields.Many2one('financiera.cobranza.config', "Configuracion")
	activo = fields.Boolean("Activo", default=True)
	partner_ids = fields.One2many('res.partner', 'mora_id', string='Clientes')
	partner_cantidad = fields.Integer("Clientes")
	dia_inicial_impago = fields.Integer("Dias inicial de impago")
	dia_final_impago = fields.Integer("Dias final de impago")
	monto = fields.Float("Monto de la cartera", digits=(16,2))
	porcentaje = fields.Float("Porcentaje de la cartera", digits=(16,2))
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('res.partner.mora'))
