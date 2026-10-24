from django import template

register = template.Library()


@register.filter
def vnd(value):
    """150000 -> 150.000đ"""
    try:
        return f"{int(value):,}đ".replace(",", ".")
    except (TypeError, ValueError):
        return value
