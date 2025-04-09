# Overview
This repository provides instructions, documentation, and examples regarding deployment of the Knowledge Lake Management System (KLMS) developed by the [STELAR project](https://stelar-project.eu/). The STELAR KLMS supports and facilitates a holistic approach for FAIR (Findable, Accessible, Interoperable, Reusable) and AI-ready (high-quality, reliably labeled) data. It allows to (semi-)automatically turn a raw data lake into a knowledge lake by: (a) enhancing the data lake with a knowledge layer; and (b) developing and integrating a set of data management tools and workflows. 
The knowledge layer comprises: (a) a data catalog that offers automatically enhanced metadata for the raw data assets in the lake; and (b) a knowledge graph that semantically describes and interlinks these data assets using suitable domain ontologies and vocabularies. The provided STELAR tools and workflows offer novel functionalities for: (a) data discovery and quality management; (b) data linking and alignment, and (c) data annotation and synthetic data generation.

![alt text](https://github.com/stelar-eu/klms-deploy/blob/main/misc/klms_architecture.png?raw=true)

## KLMS core components

* [Keycloak](https://www.keycloak.org/) is used for Identity and Access Management;

* [Data Catalog](https://github.com/stelar-eu/klms-core-components-setup/tree/main/data-catalog) of datasets in KLMS, deployed as a [CKAN](https://ckan.org/) site. Metadata about published datasets (i.e., CKAN packages and resources) is stored in a [PostgreSQL](https://www.postgresql.org/) database.	

* A Knowledge Graph is deployed via [Ontop](https://ontop-vkg.org/), employing [mappings](https://github.com/stelar-eu/klms-ontology/tree/main/mappings) from the database to a virtual RDF graph according to the [KLMS ontology](https://github.com/stelar-eu/klms-ontology).

* [MinIO](https://min.io/) serves as a storage layer for the files in the data lake.

* [Stelar Operator](https://github.com/stelar-eu/stelar-operator-airflow) necessary to design and implement workflows inside the STELAR KLMS using the [Apache Airflow](https://airflow.apache.org/) workflow engine. 

* [Dashboards](https://github.com/stelar-eu/klms-core-components-setup/tree/main/dashboard) offer a quick overview about datasets, workflows and tasks managed by the KLMS.

* A RESTful [Data API](https://github.com/stelar-eu/data-api) is used for managing and searching resources in the KLMS. 

The STELAR KLMS supports two alternative workflow engines: 

* In its Community Edition, it supports [Apache Airflow](https://airflow.apache.org/), which is a very popular open-source platform for this purpose. 

* In its Professional and Enterprise editions, it supports the [RapidMiner Studio & AI Hub](https://rapidminer.com/), which is a widely used commercial platform for machine learning and data science workflows.


## KLMS tools 

* [Synopses Data engine](https://sdeaas.github.io/) for Extreme Scale Analytics-as-a-Service.

* [GeoTriples](https://github.com/AI-team-UoA/GeoTriples) for publishing geospatial data as Linked Geospatial Data in RDF.

* [pyJedAI](https://github.com/stelar-eu/Schema-Matching-and-Entity-Linking) for Schema Matching and Entity Linking.

* [JedAI-spatial](https://github.com/AI-team-UoA/JedAI-spatial) for computing topological relations between datasets with geometric entities.

* [Correlation detective (CorDet)](https://github.com/CorrelationDetective/library) for finding interesting multivariate correlations in vector datasets.

* [Data Profiler](https://github.com/stelar-eu/data-profiler), a library for profiling different types of data and files.

* [Data Selection](https://github.com/stelar-eu/data-selection) interface for searching, ranking, and comparing datasets available in the KLMS Data Catalog.

* [GenericNER](https://github.com/stelar-eu/GenericNER) for named entity recognition (NER) on input texts.

* [FoodNER](https://github.com/stelar-eu/FoodNER), a service for detecting and extracting Name Entities from Food Science text files.

* [Synthetic Data Generation](https://github.com/stelar-eu/Synthetic-Data-Generation) for textual data in agri-food domain.

* [Hazard-classification](https://github.com/stelar-eu/Hazard-classification) from incidents reported in agri-food domain.


## Examples 

* Orchestration of several KLMS components for [entity extraction and linking](https://github.com/stelar-eu/klms-deploy/tree/main/examples/workflows) over unstructured food safety data employing Airflow workflow engine and the Data API for publishing and searching in the Data Catalog.


# License

The contents of this project are licensed under the [GPL-2.0 license](https://github.com/stelar-eu/klms-deploy/blob/main/LICENSE).
