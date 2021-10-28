# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime

class ResBankBnaCode(models.Model):
	_name = 'res.bank.bna.code'

	name = fields.Char("Nombre")
	code_bcra = fields.Char('Codigo BCRA')
	code_bna = fields.Char('Codigo BNA')

	@api.one
	def zfill_all(self):
		bna_code_obj = self.pool.get('res.bank.bna.code')
		bna_code_ids = bna_code_obj.search(self.env.cr, self.env.uid, [])
		bna_code_ids = bna_code_obj.browse(self.env.cr, self.env.uid, bna_code_ids)
		for bna_code_id in bna_code_ids:
			bna_code_id.code_bcra = bna_code_id.code_bcra.zfill(4)
	
	def code_bcra_to_bna(self, code_bcra):
		print("bucamos suc: ", code_bcra)
		code_bna = False
		bna_code_obj = self.pool.get('res.bank.bna.code')
		bna_code_ids = bna_code_obj.search(self.env.cr, self.env.uid, [
			('code_bcra', '=', code_bcra)
		])
		print("result ids: ", bna_code_ids)
		if len(bna_code_ids) > 0:
			bna_code_id = bna_code_obj.browse(self.env.cr, self.env.uid, bna_code_ids[0])
			code_bna = bna_code_id.code_bna
		return code_bna