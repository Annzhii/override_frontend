# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# GNU GPLv3 License. See license.txt
import os
import subprocess
from frappe import _
import frappe
from frappe import safe_decode
from frappe.integrations.frappe_providers.frappecloud_billing import is_fc_site
from frappe.utils import cint, get_system_timezone
from frappe.utils.telemetry import capture
from frappe.config import get_modules_from_all_apps_for_user

no_cache = 1

ALLOWED_ROLES = {"Sales User", "Sales Manager", "Sales Master Manager"}

def check_app_permission():
	if frappe.session.user == "Administrator":
		return True

	allowed_modules = get_modules_from_all_apps_for_user()
	allowed_modules = [x["module_name"] for x in allowed_modules]
	if "FCRM" not in allowed_modules:
		return False

	roles = frappe.get_roles()
	if any(
		role in ["System Manager", "Sales User", "Sales Manager"] for role in roles
	):
		return True

	return False

def get_context():

	if not check_app_permission():
		frappe.throw(
			_("You do not have permission to access this page"),
			frappe.PermissionError
		)

	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	if frappe.session.user != "Guest":
		capture("active_site", "crm")
	return context

@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw("This method is only meant for developer mode")
	return get_boot()

def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"default_route": get_default_route(),
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"setup_complete": cint(frappe.get_system_settings("setup_complete")),
			"sysdefaults": frappe.defaults.get_defaults(),
			"is_demo_site": frappe.conf.get("is_demo_site"),
			"is_fc_site": is_fc_site(),
			"timezone": {
				"system": get_system_timezone(),
				"user": frappe.db.get_value("User", frappe.session.user, "time_zone")
				or get_system_timezone(),
			},
		}
	)

def get_default_route():
	return "/crm"

def run_git_command(command):
	try:
		with open(os.devnull, "wb") as null_stream:
			result = subprocess.check_output(command, shell=True, stdin=null_stream, stderr=null_stream)
		return safe_decode(result).strip()
	except Exception:
		frappe.log_error(
			title="Git Command Error",
		)
		return ""