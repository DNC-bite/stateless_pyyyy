def puede_ver_venta(user, venta) -> bool:
    """Solo el dueño del pedido y el personal (admin y empleado) pueden verlo."""
    return user.is_authenticated and (venta.usuario_id == user.pk or user.es_personal)
