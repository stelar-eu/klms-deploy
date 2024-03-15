# Overview
This Jupyter notebook showcases how several KLMS components can be used to analyze unstructured food safety data (e.g., natural language descriptions of food safety incidents) and extract relevant entities and their relationships (e.g., hazard, product brand, company, date of incident, type of incident, origin country). This analysis will produce structured information that can then be used in downstream tasks, in particular for training ML models for risk prediction. 

In particular, this example demonstrates how users can:

* publish datasets related to food incidents in the [STELAR Data Catalog](https://github.com/stelar-eu/klms-core-components-setup/tree/main/data-catalog) using the [Data API](https://github.com/stelar-eu/data-api); 

* specify a workflow in [Apache Airflow](https://airflow.apache.org/) involving these datasets to perform entity extraction and link such entities to entities in a knowledge graph;

* invoke such a predefined workflow in Airflow and trigger its execution with a user-specified configuration;

* and finally, inspect metrics collected from workflow execution through the Data API, and also identify workflow metadata exposed in the STELAR Knowledge Graph according to the [KG ontology](https://github.com/stelar-eu/klms-ontology).