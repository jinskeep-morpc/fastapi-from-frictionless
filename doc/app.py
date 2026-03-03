
# app.py
from fastapi import Depends, FastAPI, HTTPException, Query
import fastapi
from fastapi_querybuilder import QueryBuilder
from sqlalchemy import text
from sqlmodel import Session, select
from .database import create_db_and_tables, engine
from .models import *
from sqlalchemy.ext.asyncio import AsyncSession

# Initiate app
app = FastAPI()

# Dependencies
@app.on_event('startup')
def on_startup():
    create_db_and_tables()

def get_session():
    with Session(engine) as session:
        yield session

# @app.get('/')
# def read_schema(*, session: Session = Depends(get_session)):
#     return {name.lower()}s

    
# Location requests
@app.post('/locations/', response_model=LocationPublic)
def create_location(*, session: Session = Depends(get_session), location: LocationCreate):
    location = Location.model_validate(location)
    session.add(location)
    session.commit()
    session.refresh(location)
    return location
    
@app.get('/locations/', response_model=list[LocationPublic])
def read_locations(*, session: Session = Depends(get_session)):
    locations = session.exec(select(Location)).all()
    return locations
    
@app.get('/locations/{location_address}', response_model=LocationPublic)
def read_location(*, session: Session = Depends(get_session), location_address: str):
    location = session.get(Location, location_address)
    if not location:
        raise HTTPException(status_code=404, detail='Location not found.')
    return location
    
    
@app.patch('/locations/{location_address}', response_model=LocationPublic)
def update_location(*, session: Session = Depends(get_session), location_address: str, location: LocationUpdate):
    db_location = session.get(Location, location_address)
    if not db_location:
        raise HTTPException(status_code=404, detail=f'Location {location_address} not found.')
    location_data = location.model_dump(exclude_unset=True)
    db_location.sqlmodel_update(location_data)
    session.add(db_location)
    session.commit()
    session.refresh(db_location)
    return db_location
    
@app.delete('/locations/{location_address}')
def delete_location(*, session: Session = Depends(get_session), location_address: str):
    location = session.get(Location, location_address)
    if not location:
        raise HTTPException(status_code=404, detail=f'Location {location_address} not found.')
    session.delete(location)
    session.commit()
    return {'ok': True}
    
    
# Hotspot requests
@app.post('/hotspots/', response_model=HotspotPublic)
def create_hotspot(*, session: Session = Depends(get_session), hotspot: HotspotCreate):
    hotspot = Hotspot.model_validate(hotspot)
    session.add(hotspot)
    session.commit()
    session.refresh(hotspot)
    return hotspot
    
@app.get('/hotspots/', response_model=list[HotspotPublic])
def read_hotspots(*, session: Session = Depends(get_session)):
    hotspots = session.exec(select(Hotspot)).all()
    return hotspots
    
@app.get('/hotspots/{hotspot_macaddr}', response_model=HotspotPublic)
def read_hotspot(*, session: Session = Depends(get_session), hotspot_macaddr: str):
    hotspot = session.get(Hotspot, hotspot_macaddr)
    if not hotspot:
        raise HTTPException(status_code=404, detail='Hotspot not found.')
    return hotspot
    
    
@app.patch('/hotspots/{hotspot_macaddr}', response_model=HotspotPublic)
def update_hotspot(*, session: Session = Depends(get_session), hotspot_macaddr: str, hotspot: HotspotUpdate):
    db_hotspot = session.get(Hotspot, hotspot_macaddr)
    if not db_hotspot:
        raise HTTPException(status_code=404, detail=f'Hotspot {hotspot_macaddr} not found.')
    hotspot_data = hotspot.model_dump(exclude_unset=True)
    db_hotspot.sqlmodel_update(hotspot_data)
    session.add(db_hotspot)
    session.commit()
    session.refresh(db_hotspot)
    return db_hotspot
    
@app.delete('/hotspots/{hotspot_macaddr}')
def delete_hotspot(*, session: Session = Depends(get_session), hotspot_macaddr: str):
    hotspot = session.get(Hotspot, hotspot_macaddr)
    if not hotspot:
        raise HTTPException(status_code=404, detail=f'Hotspot {hotspot_macaddr} not found.')
    session.delete(hotspot)
    session.commit()
    return {'ok': True}
    
    
# Sensor requests
@app.post('/sensors/', response_model=SensorPublic)
def create_sensor(*, session: Session = Depends(get_session), sensor: SensorCreate):
    sensor = Sensor.model_validate(sensor)
    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    return sensor
    
@app.get('/sensors/', response_model=list[SensorPublic])
def read_sensors(*, session: Session = Depends(get_session)):
    sensors = session.exec(select(Sensor)).all()
    return sensors
    
@app.get('/sensors/{sensor_macaddr}', response_model=SensorPublic)
def read_sensor(*, session: Session = Depends(get_session), sensor_macaddr: str):
    sensor = session.get(Sensor, sensor_macaddr)
    if not sensor:
        raise HTTPException(status_code=404, detail='Sensor not found.')
    return sensor
    
    
@app.patch('/sensors/{sensor_macaddr}', response_model=SensorPublic)
def update_sensor(*, session: Session = Depends(get_session), sensor_macaddr: str, sensor: SensorUpdate):
    db_sensor = session.get(Sensor, sensor_macaddr)
    if not db_sensor:
        raise HTTPException(status_code=404, detail=f'Sensor {sensor_macaddr} not found.')
    sensor_data = sensor.model_dump(exclude_unset=True)
    db_sensor.sqlmodel_update(sensor_data)
    session.add(db_sensor)
    session.commit()
    session.refresh(db_sensor)
    return db_sensor
    
@app.delete('/sensors/{sensor_macaddr}')
def delete_sensor(*, session: Session = Depends(get_session), sensor_macaddr: str):
    sensor = session.get(Sensor, sensor_macaddr)
    if not sensor:
        raise HTTPException(status_code=404, detail=f'Sensor {sensor_macaddr} not found.')
    session.delete(sensor)
    session.commit()
    return {'ok': True}
    
    
# SensorNote requests
@app.post('/sensornotes/', response_model=SensorNotePublic)
def create_sensornote(*, session: Session = Depends(get_session), sensornote: SensorNoteCreate):
    sensornote = SensorNote.model_validate(sensornote)
    session.add(sensornote)
    session.commit()
    session.refresh(sensornote)
    return sensornote
    
@app.get('/sensornotes/', response_model=list[SensorNotePublicWithAll])
def read_sensornotes(*, session: Session = Depends(get_session)):
    sensornotes = session.exec(select(SensorNote)).all()
    return sensornotes
    
@app.get('/sensornotes/{sensornote_id}', response_model=SensorNotePublicWithAll)
def read_sensornote(*, session: Session = Depends(get_session), sensornote_id: str):
    sensornote = session.get(SensorNote, sensornote_id)
    if not sensornote:
        raise HTTPException(status_code=404, detail='SensorNote not found.')
    return sensornote
    
@app.get('/sensornotes/query', response_model=list[SensorNotePublicWithAll])
async def query_sensornotes(*, session: AsyncSession = Depends(get_session), query=QueryBuilder(SensorNote)):
    sensornotes = session.execute(query)
    return sensornotes.scalars().all()
    
@app.patch('/sensornotes/{sensornote_id}', response_model=SensorNotePublic)
def update_sensornote(*, session: Session = Depends(get_session), sensornote_id: str, sensornote: SensorNoteUpdate):
    db_sensornote = session.get(SensorNote, sensornote_id)
    if not db_sensornote:
        raise HTTPException(status_code=404, detail=f'SensorNote {sensornote_id} not found.')
    sensornote_data = sensornote.model_dump(exclude_unset=True)
    db_sensornote.sqlmodel_update(sensornote_data)
    session.add(db_sensornote)
    session.commit()
    session.refresh(db_sensornote)
    return db_sensornote
    
@app.delete('/sensornotes/{sensornote_id}')
def delete_sensornote(*, session: Session = Depends(get_session), sensornote_id: str):
    sensornote = session.get(SensorNote, sensornote_id)
    if not sensornote:
        raise HTTPException(status_code=404, detail=f'SensorNote {sensornote_id} not found.')
    session.delete(sensornote)
    session.commit()
    return {'ok': True}
    
    
# Contact requests
@app.post('/contacts/', response_model=ContactPublic)
def create_contact(*, session: Session = Depends(get_session), contact: ContactCreate):
    contact = Contact.model_validate(contact)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact
    
@app.get('/contacts/', response_model=list[ContactPublic])
def read_contacts(*, session: Session = Depends(get_session)):
    contacts = session.exec(select(Contact)).all()
    return contacts
    
@app.get('/contacts/{contact_fullname}', response_model=ContactPublic)
def read_contact(*, session: Session = Depends(get_session), contact_fullname: str):
    contact = session.get(Contact, contact_fullname)
    if not contact:
        raise HTTPException(status_code=404, detail='Contact not found.')
    return contact
    
    
@app.patch('/contacts/{contact_fullname}', response_model=ContactPublic)
def update_contact(*, session: Session = Depends(get_session), contact_fullname: str, contact: ContactUpdate):
    db_contact = session.get(Contact, contact_fullname)
    if not db_contact:
        raise HTTPException(status_code=404, detail=f'Contact {contact_fullname} not found.')
    contact_data = contact.model_dump(exclude_unset=True)
    db_contact.sqlmodel_update(contact_data)
    session.add(db_contact)
    session.commit()
    session.refresh(db_contact)
    return db_contact
    
@app.delete('/contacts/{contact_fullname}')
def delete_contact(*, session: Session = Depends(get_session), contact_fullname: str):
    contact = session.get(Contact, contact_fullname)
    if not contact:
        raise HTTPException(status_code=404, detail=f'Contact {contact_fullname} not found.')
    session.delete(contact)
    session.commit()
    return {'ok': True}
    
    
# Deployment requests
@app.post('/deployments/', response_model=DeploymentPublic)
def create_deployment(*, session: Session = Depends(get_session), deployment: DeploymentCreate):
    deployment = Deployment.model_validate(deployment)
    session.add(deployment)
    session.commit()
    session.refresh(deployment)
    return deployment
    
@app.get('/deployments/', response_model=list[DeploymentPublicWithAll])
def read_deployments(*, session: Session = Depends(get_session)):
    deployments = session.exec(select(Deployment)).all()
    return deployments
    
@app.get('/deployments/{deployment_name}', response_model=DeploymentPublicWithAll)
def read_deployment(*, session: Session = Depends(get_session), deployment_name: str):
    deployment = session.get(Deployment, deployment_name)
    if not deployment:
        raise HTTPException(status_code=404, detail='Deployment not found.')
    return deployment
    
@app.get('/deployments/query', response_model=list[DeploymentPublicWithAll])
async def query_deployments(*, session: AsyncSession = Depends(get_session), query=QueryBuilder(Deployment)):
    deployments = session.execute(query)
    return deployments.scalars().all()
    
@app.patch('/deployments/{deployment_name}', response_model=DeploymentPublic)
def update_deployment(*, session: Session = Depends(get_session), deployment_name: str, deployment: DeploymentUpdate):
    db_deployment = session.get(Deployment, deployment_name)
    if not db_deployment:
        raise HTTPException(status_code=404, detail=f'Deployment {deployment_name} not found.')
    deployment_data = deployment.model_dump(exclude_unset=True)
    db_deployment.sqlmodel_update(deployment_data)
    session.add(db_deployment)
    session.commit()
    session.refresh(db_deployment)
    return db_deployment
    
@app.delete('/deployments/{deployment_name}')
def delete_deployment(*, session: Session = Depends(get_session), deployment_name: str):
    deployment = session.get(Deployment, deployment_name)
    if not deployment:
        raise HTTPException(status_code=404, detail=f'Deployment {deployment_name} not found.')
    session.delete(deployment)
    session.commit()
    return {'ok': True}
    