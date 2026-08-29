import assert from "node:assert/strict";
import test from "node:test";

import { applyApiRateLimit, serveAudio } from "./index.ts";

test("rate limits task creation by client IP", async () => {
  const rejectedLimiter = {
    async limit(options: RateLimitOptions) {
      assert.equal(options.key, "203.0.113.1");
      return { success: false };
    },
  };
  const unusedLimiter = {
    async limit() {
      assert.fail("status limiter should not be called");
      return { success: true };
    },
  };

  const response = await applyApiRateLimit(
    new Request("https://example.test/tasks", { method: "POST" }),
    "203.0.113.1",
    rejectedLimiter,
    unusedLimiter,
  );

  assert.equal(response?.status, 429);
  assert.equal(response?.headers.get("retry-after"), "60");
});

test("rate limits task status queries separately", async () => {
  const unusedLimiter = {
    async limit() {
      assert.fail("create limiter should not be called");
      return { success: true };
    },
  };
  const rejectedLimiter = {
    async limit(options: RateLimitOptions) {
      assert.equal(options.key, "203.0.113.2");
      return { success: false };
    },
  };

  const response = await applyApiRateLimit(
    new Request("https://example.test/tasks/task-id"),
    "203.0.113.2",
    unusedLimiter,
    rejectedLimiter,
  );

  assert.equal(response?.status, 429);
});

test("serves a URL-encoded OGG object with its metadata", async () => {
  const body = new TextEncoder().encode("ogg");
  const url = "https://example.test/audio/ogg/%E5%A3%B0%E9%9F%B3.ogg";
  const bucket = {
    async get(key: string, options: { range: Headers }) {
      assert.equal(key, "ogg/声音.ogg");
      const selectedBody = options.range.has("range") ? body.slice(0, 2) : body;
      return {
        body: new Blob([selectedBody]).stream(),
        httpEtag: '"etag"',
        range: { offset: 0, length: selectedBody.byteLength, suffix: undefined },
        size: body.byteLength,
        writeHttpMetadata(headers: Headers) {
          headers.set("content-type", "audio/ogg");
        },
      };
    },
  };

  const response = await serveAudio(new Request(url), bucket);

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "audio/ogg");
  assert.equal(await response.text(), "ogg");

  const rangeResponse = await serveAudio(
    new Request(url, { headers: { range: "bytes=0-1" } }),
    bucket,
  );
  assert.equal(rangeResponse.status, 206);
  assert.equal(rangeResponse.headers.get("content-range"), "bytes 0-1/3");
});
