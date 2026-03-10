
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

## Location models
class LocationBase(SQLModel):
    address: str = Field(primary_key = True)
    zipcode: int
    description: str
    neighborhood: str
    latitude: float
    longitude: float

class Location(LocationBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='locations')

class LocationCreate(LocationBase):
    pass

class LocationUpdate(LocationBase):
    address: str | None
    zipcode: int | None
    description: str | None
    neighborhood: str | None
    latitude: float | None
    longitude: float | None

class LocationPublic(LocationBase):
    created_at: datetime 
    updated_at: datetime

class LocationPublicWithAll(LocationPublic):
    deployments: Optional[List['DeploymentPublic']] | None = None

    
## LinkDeploymentContact models
class LinkDeploymentContactBase(SQLModel):
    deployment_name: str | None = Field(primary_key = True, foreign_key='deployment.name')
    contact_fullname: str | None = Field(primary_key = True, foreign_key='contact.fullname')

class LinkDeploymentContact(LinkDeploymentContactBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='linkdeploymentcontacts')
    contacts: list['Contact'] | None = Relationship(back_populates='linkdeploymentcontacts')

class LinkDeploymentContactCreate(LinkDeploymentContactBase):
    pass

class LinkDeploymentContactUpdate(LinkDeploymentContactBase):
    deployment_name: str | None
    contact_fullname: str | None

class LinkDeploymentContactPublic(LinkDeploymentContactBase):
    created_at: datetime 
    updated_at: datetime

class LinkDeploymentContactPublicWithAll(LinkDeploymentContactPublic):
    deployments: Optional[List['DeploymentPublic']] | None = None
    contacts: Optional[List['ContactPublic']] | None = None

class LinkDeploymentContactPublicWithDeployment(LinkDeploymentContactPublic):
    deployments: Optional[List['DeploymentPublic']] | None = None


class LinkDeploymentContactPublicWithContact(LinkDeploymentContactPublic):
    contacts: Optional[List['ContactPublic']] | None = None


    
## Hotspot models
class HotspotBase(SQLModel):
    macaddr: str = Field(primary_key = True)
    serialnum: str
    status: str
    ssid: str
    password: str

class Hotspot(HotspotBase, TimestampMixin, table=True):
    deployments: list['Deployment'] | None = Relationship(back_populates='hotspots')

class HotspotCreate(HotspotBase):
    pass

class HotspotUpdate(HotspotBase):
    macaddr: str | None
    serialnum: str | None
    status: str | None
    ssid: str | None
    password: str | None

class HotspotPublic(HotspotBase):
    created_at: datetime 
    updated_at: datetime

class HotspotPublicWithAll(HotspotPublic):
    deployments: Optional[List['DeploymentPublic']] | None = None

    
## Sensor models
class SensorBase(SQLModel):
    macaddr: str = Field(primary_key = True)
    name: str
    type: str | None
    status: str | None

class Sensor(SensorBase, TimestampMixin, table=True):
    registrations: list['Registration'] | None = Relationship(back_populates='sensors')
    sensornotes: list['SensorNote'] | None = Relationship(back_populates='sensors')
    deployments: list['Deployment'] | None = Relationship(back_populates='sensors')

class SensorCreate(SensorBase):
    pass

class SensorUpdate(SensorBase):
    macaddr: str | None
    name: str | None
    type: str | None
    status: str | None

class SensorPublic(SensorBase):
    created_at: datetime 
    updated_at: datetime

class SensorPublicWithAll(SensorPublic):
    registrations: Optional[List['RegistrationPublic']] | None = None
    sensornotes: Optional[List['SensorNotePublic']] | None = None
    deployments: Optional[List['DeploymentPublic']] | None = None

    
## Registration models
class RegistrationBase(SQLModel):
    macaddr: str | None
    reg_email: EmailStr | None
    outside: bool | None
    sensor_name: str | None = Field(foreign_key='sensor.name')
    public: bool | None
    latitude: float | None
    longitude: float | None
    owner_name: str | None
    owner_email: EmailStr | None
    smsalert_number: str | None

class Registration(RegistrationBase, TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sensors: list['Sensor'] | None = Relationship(back_populates='registrations')

class RegistrationCreate(RegistrationBase):
    pass

class RegistrationUpdate(RegistrationBase):
    macaddr: str | None
    reg_email: EmailStr | None
    outside: bool | None
    sensor_name: str | None
    public: bool | None
    latitude: float | None
    longitude: float | None
    owner_name: str | None
    owner_email: EmailStr | None
    smsalert_number: str | None

class RegistrationPublic(RegistrationBase):
    id: int
    created_at: datetime 
    updated_at: datetime

class RegistrationPublicWithAll(RegistrationPublic):
    sensors: Optional[List['SensorPublic']] | None = None

    
## SensorNote models
class SensorNoteBase(SQLModel):
    sensor_name: str = Field(default=None, foreign_key='sensor.name')
    date: date
    author: str
    note: str

class SensorNote(SensorNoteBase, TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sensors: list['Sensor'] | None = Relationship(back_populates='sensornotes')

class SensorNoteCreate(SensorNoteBase):
    pass

class SensorNoteUpdate(SensorNoteBase):
    sensor_name: str | None
    date: date | None
    author: str | None
    note: str | None

class SensorNotePublic(SensorNoteBase):
    id: int
    created_at: datetime 
    updated_at: datetime

class SensorNotePublicWithAll(SensorNotePublic):
    sensors: Optional[List['SensorPublic']] | None = None

    
## Contact models
class ContactBase(SQLModel):
    fullname: str = Field(primary_key = True)
    email: str | None
    phone: str | None

class Contact(ContactBase, TimestampMixin, table=True):
    linkdeploymentcontacts: list['LinkDeploymentContact'] | None = Relationship(back_populates='contacts')

class ContactCreate(ContactBase):
    pass

class ContactUpdate(ContactBase):
    fullname: str | None
    email: str | None
    phone: str | None

class ContactPublic(ContactBase):
    created_at: datetime 
    updated_at: datetime

class ContactPublicWithAll(ContactPublic):
    linkdeploymentcontacts: Optional[List['LinkDeploymentContactPublicWithDeployment']] | None = None

    
## Deployment models
class DeploymentBase(SQLModel):
    name: str = Field(primary_key = True)
    sensor_name: str = Field(default=None, foreign_key='sensor.name')
    sensor_index: int | None
    start_date: date | None
    end_date: date | None
    location_address: str | None = Field(foreign_key='location.address')
    hotspot_macaddr: str | None = Field(foreign_key='hotspot.macaddr')

class Deployment(DeploymentBase, TimestampMixin, table=True):
    linkdeploymentcontacts: list['LinkDeploymentContact'] | None = Relationship(back_populates='deployments')
    sensors: list['Sensor'] | None = Relationship(back_populates='deployments')
    locations: list['Location'] | None = Relationship(back_populates='deployments')
    hotspots: list['Hotspot'] | None = Relationship(back_populates='deployments')

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentUpdate(DeploymentBase):
    name: str | None
    sensor_name: str | None
    sensor_index: int | None
    start_date: date | None
    end_date: date | None
    location_address: str | None
    hotspot_macaddr: str | None

class DeploymentPublic(DeploymentBase):
    created_at: datetime 
    updated_at: datetime

class DeploymentPublicWithAll(DeploymentPublic):
    sensors: Optional[List['SensorPublic']] | None = None
    locations: Optional[List['LocationPublic']] | None = None
    hotspots: Optional[List['HotspotPublic']] | None = None
    linkdeploymentcontacts: Optional[List['LinkDeploymentContactPublicWithContact']] | None = None

    