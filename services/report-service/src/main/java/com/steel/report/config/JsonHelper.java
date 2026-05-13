package com.steel.report.config;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.stereotype.Component;

@Component
public class JsonHelper {

    public static final ObjectMapper MAPPER = new ObjectMapper()
        .registerModule(new JavaTimeModule());

    public String toJson(Object obj) {
        if (obj == null) return null;
        try { return MAPPER.writeValueAsString(obj); }
        catch (Exception e) { throw new RuntimeException(e); }
    }

    public <T> T fromJson(String json, Class<T> cls) {
        if (json == null) return null;
        try { return MAPPER.readValue(json, cls); }
        catch (Exception e) { throw new RuntimeException(e); }
    }

    public <T> T fromJson(String json, TypeReference<T> ref) {
        if (json == null) return null;
        try { return MAPPER.readValue(json, ref); }
        catch (Exception e) { throw new RuntimeException(e); }
    }
}
