# fastapi-from-frictionless

## Introduction

WIP - A python package which take a frictionless data package and resources and creates a sqlmodel and fastapi instance. 

Goal:
The goal is to integrate the use of relational databases and queryable APIs with our current use of frictionless and flat csv files or excel. This maintains little to no change for "customers" that are used to seeing an excel workbook, and continues to use frictionless to document and validate the fields in the workbook but also add the ability to ingest the data as a relational database, linking the meta data to other data sources and then running analysis using the API. 

Roadmap:

- [ ] From a [frictionless data package](https://datapackage.org/standard/data-package/) create [SQLmodels](https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file) for each resource with sane defaults.
- [ ] Create a [FastAPI](https://fastapi.tiangolo.com/tutorial/bigger-applications/) router for each model with all basic CRUD.
- [ ] Implement [Fast API query builder](https://github.com/bhadri01/fastapi-querybuilder) for automatic query capabilities based on models.
- [ ] Create workflow for ingesting and exporting data using excel workbook as interface.
- [ ] Optional: Implement [security measures](https://fastapi.tiangolo.com/tutorial/security/first-steps/) using headers 
- [ ] Optional: Create front-end that is a form and auto-populates fields. 
- [ ] Optional: Drawio ERD to frictionless

## Frictionless to SQLmodel

- [ ] Create template for BaseModel for table from frictionless fields.
- [ ] Create TableModel with auto-incrementing id and created_at and updated_at fields
- [ ] Create Response models
    - [ ] CreateModel
    - [ ] PublicModel
    - [ ] PublicWithRelationshipsModel
    - [ ] UpdateModel

## Create basic CRUD FastAPI router for each model

- [ ] Build template routers for each desired endpoint
    - [ ] create
    - [ ] read_all
    - [ ] read_single
    - [ ] update
    - [ ] delete

- [ ] Create app.py with APIrouter class to bring routers together.
- [ ] Create root page with default documentation

## Implement Query Builder

- [ ] Add template for query route
- [ ] Designate in frictionless resource if it should be implemented
- [ ] Optional: default routes for standard queries based on frictionless schema.

## Create workflow for excel interface

- [ ] Create empty excel workbook from data package
- [ ] Write python to update/create entries based on excel workbook
- [ ] Write python to dump all data to excel
- [ ] Optional: Create default router for GET/POST file

