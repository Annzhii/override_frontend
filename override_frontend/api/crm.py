import frappe
from frappe import _
from frappe.utils import get_url
from pushweb.api.push import send_push_to_user


from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)

@frappe.whitelist()
def add_assignments(doctype, name, assign_to):
    print (doctype)
    doctype_route_map = {
        "CRM Lead": "leads",
        "CRM Deal": "deals",
    }
    route = doctype_route_map.get(doctype)

    for user in assign_to:
        send_push_to_user(
            to_app="crm",
            user=user,
            title=("New Assignment")[:100],
            body=name,
            url=get_url(f"/crm/{route}/{name}#activiy")
        )
        
    add({"assign_to": assign_to, "doctype": doctype, "name": name}, ignore_permissions=True)
	
def assign_agent_deal(agent, name):
    if not agent:
        return

    assignees = get_assigned_users("CRM Deal", name)
    if assignees:
        for assignee in assignees:
            if agent == assignee:
                # the agent is already set as an assignee
                return

    add({"assign_to": [agent], "doctype": "CRM Deal", "name": name}, ignore_permissions=True)

def assign_agent_lead(agent, name):
    if not agent:
        return

    assignees = get_assigned_users("CRM Lead", name)
    if assignees:
        for assignee in assignees:
            if agent == assignee:
                # the agent is already set as an assignee
                return

    add({"assign_to": [agent], "doctype": "CRM Lead", "name": name}, ignore_permissions=True)

@frappe.whitelist()
def get_assigned_users(doctype, name, default_assigned_to=None):
	assigned_users = frappe.get_all(
		"Assignment",
		fields=["allocated_to"],
		filters={
			"reference_type": doctype,
			"reference_name": name,
			"status": ("!=", "Cancelled"),
		},
		pluck="allocated_to",
	)

	users = list(set(assigned_users))

	# if users is empty, add default_assigned_to
	if not users and default_assigned_to:
		users = [default_assigned_to]
	return users

@frappe.whitelist()
def remove_assignments(doctype, name, assignees, ignore_permissions=False):
	assignees = frappe.parse_json(assignees)

	if not assignees:
		return

	for assign_to in assignees:
		set_status(
			doctype,
			name,
			todo=None,
			assign_to=assign_to,
			status="Cancelled",
			ignore_permissions=ignore_permissions,
		)

def set_status(doctype, name, todo=None, assign_to=None, status="Cancelled", ignore_permissions=False):
	"""remove from todo"""

	if not ignore_permissions:
		frappe.get_doc(doctype, name).check_permission()
	try:
		if not todo:
			todo = frappe.db.get_value(
				"Assignment",
				{
					"reference_type": doctype,
					"reference_name": name,
					"allocated_to": assign_to,
					"status": ("!=", status),
				},
			)
		if todo:
			todo = frappe.get_doc("Assignment", todo)
			todo.status = status
			todo.save(ignore_permissions=True)

			notify_assignment(todo.assigned_by, todo.allocated_to, todo.reference_type, todo.reference_name)
	except frappe.DoesNotExistError:
		pass

	# clear assigned_to if field exists
	if frappe.get_meta(doctype).get_field("assigned_to") and status in ("Cancelled", "Closed"):
		frappe.db.set_value(doctype, name, "assigned_to", None)

	return get({"doctype": doctype, "name": name})

def notify_assignment(assigned_by, allocated_to, doc_type, doc_name, action="CLOSE", description=None):
	"""
	Notify assignee that there is a change in assignment
	"""
	if not (assigned_by and allocated_to and doc_type and doc_name):
		return

	assigned_user = frappe.db.get_value("User", allocated_to, ["language", "enabled"], as_dict=True)

	# return if self assigned or user disabled
	if assigned_by == allocated_to or not assigned_user.enabled:
		return

	# Search for email address in description -- i.e. assignee
	user_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
	title = get_title(doc_type, doc_name)
	description_html = f"<div>{description}</div>" if description else None

	if action == "CLOSE":
		subject = _("Your assignment on {0} {1} has been removed by {2}", lang=assigned_user.language).format(
			frappe.bold(_(doc_type)), get_title_html(title), frappe.bold(user_name)
		)
	else:
		user_name = frappe.bold(user_name)
		document_type = frappe.bold(_(doc_type, lang=assigned_user.language))
		title = get_title_html(title)
		subject = _("{0} assigned a new task {1} {2} to you", lang=assigned_user.language).format(
			user_name, document_type, title
		)

	notification_doc = {
		"type": "Assignment",
		"document_type": doc_type,
		"subject": subject,
		"document_name": doc_name,
		"from_user": frappe.session.user,
		"email_content": description_html,
	}

	enqueue_create_notification(allocated_to, notification_doc)
	
def get(args=None):
	"""get assigned to"""
	if not args:
		args = frappe.local.form_dict

	return frappe.get_all(
		"Assignment",
		fields=["allocated_to as owner", "name"],
		filters={
			"reference_type": args.get("doctype"),
			"reference_name": args.get("name"),
			"status": ("not in", ("Cancelled", "Closed")),
		},
		limit=5,
	)

@frappe.whitelist()
def add(args=None, *, ignore_permissions=False):
	"""add in someone's to do list
	args = {
	        "assign_to": [],
	        "doctype": ,
	        "name": ,
	        "description": ,
	        "assignment_rule":
	}

	"""
	if not args:
		args = frappe.local.form_dict

	users_with_duplicate_todo = []
	shared_with_users = []

	for assign_to in frappe.parse_json(args.get("assign_to")):
		filters = {
			"reference_type": args["doctype"],
			"reference_name": args["name"],
			"status": "Open",
			"allocated_to": assign_to,
		}
		if not ignore_permissions:
			frappe.get_doc(args["doctype"], args["name"]).check_permission()

		if frappe.get_all("Assignment", filters=filters):
			users_with_duplicate_todo.append(assign_to)
		else:
			from frappe.utils import nowdate

			description = args.get("description") or ""
			has_content = strip_html(description) or "<img" in description
			if not has_content:
				args["description"] = _("Assignment for {0} {1}").format(args["doctype"], args["name"])

			d = frappe.get_doc(
				{
					"doctype": "Assignment",
					"allocated_to": assign_to,
					"reference_type": args["doctype"],
					"reference_name": str(args["name"]),
					"description": args.get("description"),
					"priority": args.get("priority", "Medium"),
					"status": "Open",
					"date": args.get("date", nowdate()),
					"assigned_by": args.get("assigned_by", frappe.session.user),
					"assignment_rule": args.get("assignment_rule"),
				}
			).insert(ignore_permissions=True)

			# set assigned_to if field exists
			if frappe.get_meta(args["doctype"]).get_field("assigned_to"):
				frappe.db.set_value(args["doctype"], args["name"], "assigned_to", assign_to)

			doc = frappe.get_doc(args["doctype"], args["name"])

			# if assignee does not have permissions, share or inform
			if not frappe.has_permission(doc=doc, user=assign_to):
				if frappe.get_system_settings("disable_document_sharing"):
					msg = _("User {0} is not permitted to access this document.").format(
						frappe.bold(assign_to)
					)
					msg += "<br>" + _(
						"As document sharing is disabled, please give them the required permissions before assigning."
					)
					frappe.throw(msg, title=_("Missing Permission"))
				else:
					frappe.share.add(doc.doctype, doc.name, assign_to)
					shared_with_users.append(assign_to)

			# make this document followed by assigned user
			if frappe.get_cached_value("User", assign_to, "follow_assigned_documents"):
				follow_document(args["doctype"], args["name"], assign_to)

			# notify
			notify_assignment(
				d.assigned_by,
				d.allocated_to,
				d.reference_type,
				d.reference_name,
				action="ASSIGN",
				description=args.get("description"),
			)

	if shared_with_users:
		user_list = format_message_for_assign_to(shared_with_users)
		frappe.msgprint(
			_("Shared with the following Users with Read access:{0}").format(user_list, alert=True)
		)

	if users_with_duplicate_todo:
		user_list = format_message_for_assign_to(users_with_duplicate_todo)
		frappe.msgprint(_("Already in the following Users ToDo list:{0}").format(user_list, alert=True))

	return get(args)

def format_message_for_assign_to(users):
	return "<br><br>" + "<br>".join(users)

from frappe.utils.data import strip_html
from frappe.desk.form.document_follow import follow_document