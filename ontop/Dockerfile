#
# The ontop custom STELAR image
#

#
# Helper stage
#
FROM ontop/ontop:5.0.0 as  ontop-workspace
ARG JDBC_DRIVER=postgresql-42.7.3.jar

#
# Final stage
#
USER 0
WORKDIR /
RUN apt -y update
RUN apt -y install git
RUN git clone https://github.com/stelar-eu/klms-ontology
RUN git clone https://github.com/stelar-eu/klms-core-components-setup
RUN  wget https://jdbc.postgresql.org/download/postgresql-42.7.3.jar


FROM ontop/ontop:5.0.0

USER 0

RUN  mkdir -p /opt/ontop/jdbc
COPY --from=ontop-workspace /postgresql-42.7.3.jar /opt/ontop/jdbc
ENV ONTOP_DB_DRIVER=org.postgresql.Driver

RUN  mkdir -p /opt/ontop/input
COPY --from=ontop-workspace  /klms-ontology/mappings/klms-mappings.obda /opt/ontop/input
ENV ONTOP_MAPPING_FILE=/opt/ontop/input/klms-mappings.obda

COPY --from=ontop-workspace /klms-core-components-setup/knowledge-graph/input/klms-sparql-portal.toml /opt/ontop/input
ENV ONTOP_PORTAL_FILE=/opt/ontop/input/klms-sparql-portal.toml

#COPY --from=ontop-workspace /klms-ontology/serializations/klms-ontology.ttl /opt/ontop/input
#ENV ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-ontology.ttl
#COPY --from=ontop-workspace /klms-ontology/klms-model.owl /opt/ontop/input
#ENV ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-model.owl

