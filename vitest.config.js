import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    // Mesma configuracao que o antigo tests/frontend/setup.js passava
    // manualmente para `new JSDOM(...)`: origem http (nao "file:"/opaque, que
    // faz localStorage lancar SecurityError) e pretendToBeVisual (necessario
    // para requestAnimationFrame, usado em architecture.js).
    environmentOptions: {
      jsdom: {
        url: "http://localhost/",
        pretendToBeVisual: true
      }
    },
    include: ["tests/frontend/**/*.test.js"],
    reporters: ["default", "junit"],
    outputFile: {
      junit: "artifacts/vitest-junit.xml"
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "lcov"],
      reportsDirectory: "artifacts/coverage-frontend"
    }
  }
});
