from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.config import settings
from app.models import Brand, City, OsmImportBatch, OsmImportPoint, Restaurant
from app.schemas import (
    OsmImportBatchOut,
    OsmImportCommitIn,
    OsmImportCommitOut,
    OsmImportCreateIn,
    OsmImportPointOut,
    OsmImportPointPatch,
)
from app.services.osm import OsmError, find_restaurants
from app.services.receipt import distance_m
from app.services.scope import Scope, city_key, normalize_city, require_staff

router = APIRouter(prefix="/admin/osm-imports", tags=["admin", "osm-imports"])


def _purge_expired(db: Session) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.osm_import_ttl_days)
    db.execute(delete(OsmImportBatch).where(OsmImportBatch.created_at < cutoff))


def _load(db: Session, batch_id: int) -> OsmImportBatch | None:
    return db.scalar(
        select(OsmImportBatch)
        .options(joinedload(OsmImportBatch.brand), selectinload(OsmImportBatch.points))
        .where(OsmImportBatch.id == batch_id)
    )


def _duplicate(restaurants: list[Restaurant], address: str, lat: float, lng: float) -> Restaurant | None:
    address_key = " ".join(address.casefold().split())
    for restaurant in restaurants:
        if " ".join(restaurant.address.casefold().split()) == address_key:
            return restaurant
        if distance_m(lat, lng, restaurant.lat, restaurant.lng) <= 80:
            return restaurant
    return None


@router.get("", response_model=list[OsmImportBatchOut])
def list_imports(scope: Scope = Depends(require_staff), db: Session = Depends(get_db)):
    _purge_expired(db)
    db.commit()
    stmt = select(OsmImportBatch).options(
        joinedload(OsmImportBatch.brand), selectinload(OsmImportBatch.points)
    ).order_by(OsmImportBatch.created_at.desc()).limit(30)
    batches = db.scalars(stmt).unique().all()
    return [batch for batch in batches if scope.allows(batch.city)]


@router.post("", response_model=OsmImportBatchOut, status_code=status.HTTP_201_CREATED)
def create_import(
    payload: OsmImportCreateIn,
    scope: Scope = Depends(require_staff),
    db: Session = Depends(get_db),
):
    city = normalize_city(payload.city)
    scope.require(city, "Импорт")
    known_city = db.scalar(select(City).where(City.key == city_key(city)))
    if known_city is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Сначала добавьте город в справочник")
    brand = db.get(Brand, payload.brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    query = (payload.query or brand.name).strip()
    try:
        found = find_restaurants(city, query)
    except OsmError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(error)) from None

    existing = db.scalars(select(Restaurant).where(
        Restaurant.brand_id == brand.id,
        func.lower(func.trim(Restaurant.city)) == city_key(city),
    )).all()
    batch = OsmImportBatch(
        brand_id=brand.id, city=city, query=query, created_by_id=scope.user.id
    )
    for item in found:
        duplicate = _duplicate(existing, item.address, item.lat, item.lng)
        batch.points.append(
            OsmImportPoint(
                osm_type=item.osm_type,
                osm_id=item.osm_id,
                title=item.title,
                address=item.address,
                lat=item.lat,
                lng=item.lng,
                duplicate_restaurant_id=duplicate.id if duplicate else None,
            )
        )
    db.add(batch)
    db.commit()
    return _load(db, batch.id)


@router.get("/{batch_id}", response_model=OsmImportBatchOut)
def get_import(batch_id: int, scope: Scope = Depends(require_staff), db: Session = Depends(get_db)):
    batch = _load(db, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Импорт не найден")
    scope.require(batch.city, "Импорт")
    return batch


@router.patch("/{batch_id}/points/{point_id}", response_model=OsmImportPointOut)
def patch_import_point(
    batch_id: int,
    point_id: int,
    payload: OsmImportPointPatch,
    scope: Scope = Depends(require_staff),
    db: Session = Depends(get_db),
):
    batch = _load(db, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Импорт не найден")
    scope.require(batch.city, "Импорт")
    point = next((item for item in batch.points if item.id == point_id), None)
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    if point.imported_restaurant_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Точка уже импортирована")
    point.address = payload.address.strip()
    point.title = (payload.title or "").strip() or point.address
    existing = list(db.scalars(select(Restaurant).where(
        Restaurant.brand_id == batch.brand_id,
        func.lower(func.trim(Restaurant.city)) == city_key(batch.city),
    )))
    duplicate = _duplicate(existing, point.address, point.lat, point.lng)
    point.duplicate_restaurant_id = duplicate.id if duplicate else None
    db.commit()
    db.refresh(point)
    return point


@router.post("/{batch_id}/commit", response_model=OsmImportCommitOut)
def commit_import(
    batch_id: int,
    payload: OsmImportCommitIn,
    scope: Scope = Depends(require_staff),
    db: Session = Depends(get_db),
):
    batch = _load(db, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Импорт не найден")
    scope.require(batch.city, "Импорт")
    selected = set(payload.point_ids)
    points = [point for point in batch.points if point.id in selected]
    if len(points) != len(selected):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="В списке есть точки из другого импорта")
    existing = list(db.scalars(select(Restaurant).where(
        Restaurant.brand_id == batch.brand_id,
        func.lower(func.trim(Restaurant.city)) == city_key(batch.city),
    )))
    imported = skipped = 0
    for point in points:
        if point.address == "Адрес не указан в OSM":
            skipped += 1
            continue
        if point.imported_restaurant_id is not None or _duplicate(existing, point.address, point.lat, point.lng):
            skipped += 1
            continue
        restaurant = Restaurant(
            brand_id=batch.brand_id,
            title=point.title or point.address,
            city=batch.city,
            address=point.address,
            lat=point.lat,
            lng=point.lng,
            is_active=True,
        )
        db.add(restaurant)
        db.flush()
        point.imported_restaurant_id = restaurant.id
        existing.append(restaurant)
        imported += 1
    db.commit()
    return OsmImportCommitOut(imported=imported, skipped=skipped)


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_import(batch_id: int, scope: Scope = Depends(require_staff), db: Session = Depends(get_db)):
    batch = db.get(OsmImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Импорт не найден")
    scope.require(batch.city, "Импорт")
    db.delete(batch)
    db.commit()
