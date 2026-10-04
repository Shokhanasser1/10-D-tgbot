"""Who may do what in the admin panel (Spec 7 §3). The only place roles map to permissions.

Routes ask for one permission each. Permissions in CONFIRMATION_REQUIRED move money or change
who is an admin: they also need the password re-entered within the last few minutes, whatever
the role, the owner included.
"""

from app.models.enums import AdminRole, Permission

P = Permission

_VIEW_ALL = frozenset(
    {P.summary_view, P.catalog_view, P.orders_view, P.couriers_view},
)

ROLE_PERMISSIONS: dict[AdminRole, frozenset[Permission]] = {
    AdminRole.owner: frozenset(Permission),
    AdminRole.manager: frozenset(Permission) - {P.refunds_manage, P.admins_manage},
    AdminRole.catalog_manager: frozenset({P.catalog_view, P.catalog_edit, P.taxonomy_edit}),
    AdminRole.dispatcher: frozenset(
        {P.orders_view, P.orders_cancel_unpaid, P.couriers_view, P.couriers_manage}
    ),
    AdminRole.accountant: frozenset(
        {P.summary_view, P.orders_view, P.orders_cancel_paid, P.refunds_manage}
    ),
    AdminRole.viewer: _VIEW_ALL,
    # Gains its own catalog only together with the scope that confines it there (Spec 9 §4).
    AdminRole.seller: frozenset(),
}

CONFIRMATION_REQUIRED = frozenset({P.orders_cancel_paid, P.refunds_manage, P.admins_manage})


def permissions_of(role: AdminRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def roles_with(permission: Permission) -> tuple[AdminRole, ...]:
    """Every role holding `permission` (e.g. who to notify about something)."""
    return tuple(role for role, granted in ROLE_PERMISSIONS.items() if permission in granted)
