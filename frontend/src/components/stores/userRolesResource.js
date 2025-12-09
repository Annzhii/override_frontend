import { createResource } from 'frappe-ui'

export const userRolesResource = createResource({
  url: 'override_frontend.api.get_user_roles',
  auto: true,
})