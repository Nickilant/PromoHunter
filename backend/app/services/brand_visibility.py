from app.models import Brand, User, UserRole


def can_see_private_brands(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.admin, UserRole.moderator)


def brand_is_visible(brand: Brand, user: User | None) -> bool:
    return brand.is_public or can_see_private_brands(user)
