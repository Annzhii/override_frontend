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

no_cache = 1

ALLOWED_ROLES = {"Sales User", "Sales Manager", "Sales Master Manager"}

def get_context():
    # 获取当前用户角色
    user_roles = set(frappe.get_roles(frappe.session.user))
    
    # 如果不在允许列表中，直接抛异常
    if not user_roles.intersection(ALLOWED_ROLES):
        frappe.throw(_("You do not have permission to access this page."), frappe.PermissionError)

    # 正常返回上下文
    context = frappe._dict()
    context.boot = get_boot()

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