
from typing import Optional, List
from uuid import UUID
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel
from datetime import date, datetime, timezone, time, timedelta
from pydantic import EmailStr, AnyUrl, Json
from geoalchemy2.types import Geometry

def utcnow():
    '''Returns the current time in UTC.'''
    return datetime.now(timezone.utc)

class TimestampMixin: # https://www.davidmuraya.com/blog/reusable-sqlmodel-mixins/
    '''A mixin to add created_at and updated_at timestamp fields to a model.'''

    created_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow},
        sa_type=DateTime(timezone=True)
    )

## Sensor models
class SensorBase(SQLModel):
    macaddr: str = Field(primary_key = True)
    name: str
    type: str | None
    status: str | None

class Sensor(SensorBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='sensor')
    sensornotes: list['SensorNote'] | None = Relationship(back_populates='sensor')

class SensorCreate(SensorBase):
    pass

class SensorPublic(SensorBase):
    created_at: datetime
    updated_at: datetime


class SensorUpdate(SensorBase):
    name: str | None
    type: str | None
    status: str | None

    
## Deployment models
class DeploymentBase(SQLModel):
    name: str = Field(primary_key = True)
    sensor_name: str
    sensor_index: int | None
    start_date: date | None
    end_date: date | None
    location_address: str | None
    hotspot_macaddr: str | None
    contact_fullname: str | None

class Deployment(DeploymentBase, TimestampMixin, table=True):
    pass

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentPublic(DeploymentBase):
    created_at: datetime
    updated_at: datetime

class DeploymentPublicWithAll(DeploymentPublic):
    locations: list['Location'] | None
    contacts: list['Contact'] | None
    hotspots: list['Hotspot'] | None
    sensors: list['Sensor'] | None

class DeploymentUpdate(DeploymentBase):
    sensor_name: str | None
    sensor_index: int | None
    start_date: date | None
    end_date: date | None
    location_address: str | None
    hotspot_macaddr: str | None
    contact_fullname: str | None

    
## Contact models
class ContactBase(SQLModel):
    fullname: str = Field(primary_key = True)
    email: str | None
    phone: str | None

class Contact(ContactBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='contact')

class ContactCreate(ContactBase):
    pass

class ContactPublic(ContactBase):
    created_at: datetime
    updated_at: datetime


class ContactUpdate(ContactBase):
    email: str | None
    phone: str | None

    
## Hotspot models
class HotspotBase(SQLModel):
    macaddr: str = Field(primary_key = True)
    serialnum: str
    status: str
    ssid: float
    password: float

class Hotspot(HotspotBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='hotspot')

class HotspotCreate(HotspotBase):
    pass

class HotspotPublic(HotspotBase):
    created_at: datetime
    updated_at: datetime


class HotspotUpdate(HotspotBase):
    serialnum: str | None
    status: str | None
    ssid: float | None
    password: float | None

    
## SensorNote models
class SensorNoteBase(SQLModel):
    sensor_name: str
    date: date
    author: str
    note: str

class SensorNote(SensorNoteBase, TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)

class SensorNoteCreate(SensorNoteBase):
    pass

class SensorNotePublic(SensorNoteBase):
    id: int
    created_at: datetime
    updated_at: datetime

class SensorNotePublicWithAll(SensorNotePublic):
    sensors: list['Sensor'] | None

class SensorNoteUpdate(SensorNoteBase):
    sensor_name: str | None
    date: date | None
    author: str | None
    note: str | None

    
## Location models
class LocationBase(SQLModel):
    address: str = Field(primary_key = True)
    zipcode: int
    neighborhood: str
    description: str
    latitude: float
    longitude: float

class Location(LocationBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='location')

class LocationCreate(LocationBase):
    pass

class LocationPublic(LocationBase):
    created_at: datetime
    updated_at: datetime


class LocationUpdate(LocationBase):
    zipcode: int | None
    neighborhood: str | None
    description: str | None
    latitude: float | None
    longitude: float | None

    