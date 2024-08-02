package eu.europa.esig.dss.web;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.PropertySource;
import org.springframework.boot.web.servlet.support.SpringBootServletInitializer;

@SpringBootApplication
@PropertySource("classpath:dss.properties")
@ComponentScan(basePackages = {"eu.europa.esig.dss"})
public class DssDemoApplication extends SpringBootServletInitializer {

    public static void main(String[] args) {
        SpringApplication.run(DssDemoApplication.class, args);
    }

}
