FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /build/target/billing-service-*.jar app.jar
# 把 billing-lua 脚本一起打入镜像 (生产可挂卷覆盖)
COPY --from=build /build/src/main/resources/billing-lua /app/billing-lua
ENV TZ=Asia/Shanghai
ENV LUA_DIR=/app/billing-lua
EXPOSE 8081
ENTRYPOINT ["java","-jar","/app/app.jar"]
