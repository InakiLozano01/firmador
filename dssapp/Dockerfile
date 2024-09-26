# Stage 1: Build dependencies
FROM maven:3.9.5-eclipse-temurin-17 as dependencies

# Set the working directory
WORKDIR /usr/src/mymaven/dss-demonstrations

# Copy the pom.xml files
COPY pom.xml /usr/src/mymaven/dss-demonstrations/pom.xml
COPY dss-demo-webapp/pom.xml /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/pom.xml

# Download dependencies and cache them
RUN mvn dependency:go-offline -pl dss-demo-webapp -P quick

# Stage 2: Build application
FROM maven:3.9.5-eclipse-temurin-17 as build

# Set the working directory
WORKDIR /usr/src/mymaven/dss-demonstrations

# Copy the local repository from the previous stage to cache dependencies
COPY --from=dependencies /root/.m2 /root/.m2

# Copy the project files
COPY pom.xml /usr/src/mymaven/dss-demonstrations/
COPY dss-demo-webapp/pom.xml /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/
COPY dss-demo-webapp/src /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/src

# Package the application
RUN mvn package -pl dss-demo-webapp -P quick

# Stage 3: Run application with Tomcat
FROM tomcat:10

# Copy the built war file to the Tomcat webapps directory
COPY --from=build /usr/src/mymaven/dss-demonstrations/dss-demo-webapp/target/dss-demo-webapp-*.war /usr/local/tomcat/webapps/ROOT.war

# Expose port 5555
EXPOSE 5555

# Ensure Tomcat runs on port 5555
RUN sed -i 's/port="8080"/port="5555"/' /usr/local/tomcat/conf/server.xml

# Start Tomcat
CMD ["catalina.sh", "run"]
