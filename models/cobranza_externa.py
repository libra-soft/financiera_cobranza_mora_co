# -*- coding: utf-8 -*-

from openerp import models, fields

class FinancieraCobranzaNotificacion(models.Model):
	_name = 'financiera.cobranza.externa'

	name = fields.Char("Nombre")
	partner_ids = fields.One2many('res.partner', 'cobranza_externa_id', 'Deudores')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.externa'))


