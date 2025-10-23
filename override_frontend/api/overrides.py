import frappe
from override_frontend.api.crm import assign_agent_lead, assign_agent_deal
from crm.fcrm.doctype.crm_deal.crm_deal import CRMDeal
from crm.fcrm.doctype.crm_lead.crm_lead import CRMLead
from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import add_status_change_log

class VONTOCCRMDeal(CRMDeal):
	def after_insert(self):
		if self.deal_owner:
			assign_agent_deal(self.deal_owner, self.name)
	def validate(self):
		self.set_primary_contact()
		self.set_primary_email_mobile_no()
		if not self.is_new() and self.has_value_changed("deal_owner") and self.deal_owner:
			self.share_with_agent(self.deal_owner)
			assign_agent_deal(self.deal_owner, self.name)
		if self.has_value_changed("status"):
			add_status_change_log(self)
			if frappe.db.get_value("CRM Deal Status", self.status, "type") == "Won":
				self.closed_date = frappe.utils.nowdate()
		self.validate_forecasting_fields()
		self.validate_lost_reason()
		self.update_exchange_rate()

class VONTOCCRMLead(CRMLead):
	def after_insert(self):
		if self.lead_owner:
			assign_agent_lead(self.lead_owner, self.name)
	def validate(self):
		self.set_full_name()
		self.set_lead_name()
		self.set_title()
		self.validate_email()
		if not self.is_new() and self.has_value_changed("lead_owner") and self.lead_owner:
			self.share_with_agent(self.lead_owner,self.name)
			assign_agent_lead(self.lead_owner)
		if self.has_value_changed("status"):
			add_status_change_log(self)