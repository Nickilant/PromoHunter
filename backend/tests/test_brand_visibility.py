from pathlib import Path

from app.auth import create_access_token
from app.config import settings
from app.models import Brand, Promotion, PromotionItem, Restaurant, User, UserRole


def headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_hidden_brand_is_visible_only_to_staff(client, db):
    public = Brand(name="Открытая сеть", slug="public", is_public=True)
    hidden = Brand(name="Скрытая сеть", slug="hidden", is_public=False)
    db.add_all([public, hidden])
    db.flush()
    public_restaurant = Restaurant(
        brand_id=public.id, city="Москва", address="Открытая, 1", lat=55.7, lng=37.6
    )
    hidden_restaurant = Restaurant(
        brand_id=hidden.id, city="Москва", address="Скрытая, 2", lat=55.8, lng=37.7
    )
    db.add_all([public_restaurant, hidden_restaurant])
    db.add_all(
        [
            Promotion(brand_id=public.id, title="Открытая акция", items=[PromotionItem(name="А")]),
            Promotion(brand_id=hidden.id, title="Скрытая акция", items=[PromotionItem(name="Б")]),
        ]
    )
    user = User(phone="+79000000001", password_hash="x", display_name="Пользователь")
    moderator = User(
        phone="+79000000002",
        password_hash="x",
        display_name="Модератор",
        role=UserRole.moderator,
    )
    db.add_all([user, moderator])
    db.commit()

    for headers in ({}, headers_for(user)):
        assert [item["name"] for item in client.get("/api/brands", headers=headers).json()] == [
            "Открытая сеть"
        ]
        restaurants = client.get("/api/restaurants?city=Москва", headers=headers).json()
        assert [item["id"] for item in restaurants] == [public_restaurant.id]
        assert client.get(f"/api/restaurants/{hidden_restaurant.id}", headers=headers).status_code == 404

    staff_headers = headers_for(moderator)
    assert len(client.get("/api/brands", headers=staff_headers).json()) == 2
    assert client.get(
        f"/api/restaurants/{hidden_restaurant.id}", headers=staff_headers
    ).status_code == 200


def test_admin_can_upload_brand_logo(client, db, tmp_path, monkeypatch):
    admin = User(
        phone="+79000000003",
        password_hash="x",
        display_name="Администратор",
        role=UserRole.admin,
    )
    db.add(admin)
    db.commit()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    response = client.post(
        "/api/admin/brand-logos",
        headers=headers_for(admin),
        files={"logo": ("logo.png", b"\x89PNG\r\n\x1a\ncontent", "image/png")},
    )

    assert response.status_code == 201, response.text
    logo_url = response.json()["logo_url"]
    assert logo_url.startswith("/api/uploads/brand-logos/")
    assert (Path(tmp_path) / "brand-logos" / logo_url.rsplit("/", 1)[-1]).is_file()
