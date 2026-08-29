const PRIVATE_ORIGIN = "http://127.0.0.1:12451";
const AUDIO_PREFIX = "/audio/";
const CLIENT_IP_HEADER = "x-client-ip";

type AudioObject = Pick<
  R2ObjectBody,
  "body" | "httpEtag" | "range" | "size" | "writeHttpMetadata"
>;

type AudioBucket = {
  get(key: string, options: { range: Headers }): Promise<AudioObject | null>;
};

type RequestRateLimiter = Pick<RateLimit, "limit">;

export async function applyApiRateLimit(
  request: Request,
  clientIp: string,
  createTaskLimiter: RequestRateLimiter,
  taskStatusLimiter: RequestRateLimiter,
): Promise<Response | null> {
  const { pathname } = new URL(request.url);
  let limiter: RequestRateLimiter | null = null;
  if (request.method === "POST" && pathname === "/tasks") {
    limiter = createTaskLimiter;
  } else if (request.method === "GET" && /^\/tasks\/[^/]+$/.test(pathname)) {
    limiter = taskStatusLimiter;
  }

  if (limiter === null || (await limiter.limit({ key: clientIp })).success) {
    return null;
  }
  return Response.json(
    { error: "rate limit exceeded" },
    { status: 429, headers: { "retry-after": "60" } },
  );
}

export async function serveAudio(
  request: Request,
  bucket: AudioBucket,
): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", {
      status: 405,
      headers: { allow: "GET, HEAD" },
    });
  }

  let key: string;
  try {
    key = decodeURIComponent(new URL(request.url).pathname.slice(AUDIO_PREFIX.length));
  } catch {
    return new Response("Not found", { status: 404 });
  }
  if (!/^(wav\/[^/]+\.wav|ogg\/[^/]+\.ogg)$/.test(key)) {
    return new Response("Not found", { status: 404 });
  }

  const object = await bucket.get(key, { range: request.headers });
  if (object === null) {
    return new Response("Not found", { status: 404 });
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("accept-ranges", "bytes");
  headers.set("etag", object.httpEtag);
  if (!headers.has("cache-control")) {
    headers.set("cache-control", "public, max-age=86400");
  }

  let status = 200;
  if (request.headers.has("range") && object.range) {
    let offset = 0;
    let length = object.size;
    if ("suffix" in object.range && object.range.suffix !== undefined) {
      offset = Math.max(0, object.size - object.range.suffix);
      length = object.size - offset;
    } else {
      if ("offset" in object.range) {
        offset = object.range.offset ?? 0;
      }
      if ("length" in object.range) {
        length = object.range.length ?? object.size - offset;
      }
    }
    headers.set("content-range", `bytes ${offset}-${offset + length - 1}/${object.size}`);
    status = 206;
  }

  return new Response(request.method === "HEAD" ? null : object.body, {
    status,
    headers,
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const incomingUrl = new URL(request.url);
    if (incomingUrl.pathname.startsWith(AUDIO_PREFIX)) {
      return serveAudio(request, env.AUDIO);
    }

    const clientIp = request.headers.get("cf-connecting-ip") ?? "unknown";
    const rateLimited = await applyApiRateLimit(
      request,
      clientIp,
      env.CREATE_TASK_RATE_LIMITER,
      env.TASK_STATUS_RATE_LIMITER,
    );
    if (rateLimited !== null) {
      return rateLimited;
    }

    const targetUrl = new URL(incomingUrl.pathname + incomingUrl.search, PRIVATE_ORIGIN);
    const headers = new Headers(request.headers);
    headers.set(CLIENT_IP_HEADER, clientIp);
    const proxyRequest = new Request(targetUrl, {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual",
    });

    try {
      return await env.GENIE_API.fetch(proxyRequest);
    } catch (error) {
      console.error(JSON.stringify({
        message: "private origin unavailable",
        error: error instanceof Error ? error.message : String(error),
      }));
      return Response.json({ error: "private origin unavailable" }, { status: 502 });
    }
  },
} satisfies ExportedHandler<Env>;
