#
# The ontop custom STELAR image
#

#
# Helper stage
#
FROM ontop/ontop as  ontop-workspace
ARG JDBC_DRIVER=postgresql-42.7.3.jar

#
# Final stage
#
USER 0
WORKDIR /
RUN apt -y update
RUN apt -y install git
RUN git clone https://github.com/stelar-eu/klms-ontology
RUN  wget https://jdbc.postgresql.org/download/${JDBC_DRIVER}

FROM ontop/ontop

USER 0

RUN  mkdir -p /opt/ontop/jdbc
COPY --from=ontop-workspace /${JDBC_DRIVER} /opt/ontop/jdbc
ENV ONTOP_DB_DRIVER=org.postgresql.Driver

RUN  mkdir -p /opt/ontop/input
COPY --from=ontop-workspace  /klms-ontology/mappings/klms-mappings.obda /opt/ontop/input
ENV ONTOP_MAPPING_FILE=/opt/ontop/input/klms-mappings.obda


COPY --from=ontop-workspace /klms-ontology/serializations/klms-ontology.ttl /opt/ontop/input
ENV ONTOP_ONTOLOGY_FILE=/opt/ontop/input/klms-ontology.ttl

