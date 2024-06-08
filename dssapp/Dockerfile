FROM maven:3.9.5-eclipse-temurin-17 as build

COPY pom.xml /usr/src/mymaven/dss-demonstrations/

COPY dss-demo-webapp/pom.xml /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/
COPY dss-demo-webapp/src /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/src

COPY dss-demo-bundle/pom.xml /usr/src/mymaven/dss-demonstrations/dss-demo-bundle/


# OPTIONAL: provide documentation + javaDoc (change "pathTo")
#COPY pathTo/generated-docs /usr/src/mymaven/dss/dss-cookbook/target/generated-docs
#COPY pathTo/site/apidocs /usr/src/mymaven/dss/target/site/apidocs

WORKDIR /usr/src/mymaven/dss-demonstrations

RUN mvn package -pl dss-demo-webapp -P quick


FROM tomcat:10

COPY --from=build /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/target/dss-demo-webapp-*.war /usr/local/tomcat/webapps/ROOT.war

EXPOSE 5555

# Ensure Tomcat runs on port 5555
RUN sed -i 's/port="8080"/port="5555"/' /usr/local/tomcat/conf/server.xml

CMD ["catalina.sh", "run"]