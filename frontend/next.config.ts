import type { NextConfig } from "next";

function envFlag(name: string): boolean {
  return ["1", "true", "yes"].includes((process.env[name] || "").trim().toLowerCase());
}

function validateProductionApiOrigin() {
  if (process.env.NODE_ENV !== "production") return;

  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is required for production builds. Refusing to compile a release that would fall back to localhost:8000."
    );
  }

  // The Docker single-origin gateway deliberately uses `/` so browser requests
  // stay on the exact origin that served the frontend. This exception is only
  // enabled by an explicit build-time flag; arbitrary relative API paths remain
  // rejected by the normal production-origin contract.
  if (raw === "/") {
    if (!envFlag("PRODAGENTIC_SAME_ORIGIN_GATEWAY")) {
      throw new Error(
        "NEXT_PUBLIC_API_URL=/ is allowed only with PRODAGENTIC_SAME_ORIGIN_GATEWAY=true."
      );
    }
    return;
  }

  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("NEXT_PUBLIC_API_URL must be an absolute http(s) URL.");
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("NEXT_PUBLIC_API_URL must use http or https.");
  }

  const loopback = ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname);
  if (!loopback && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_API_URL must use HTTPS for non-local production origins.");
  }

  if (
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must be a clean backend origin without credentials, path, query parameters, or fragments."
    );
  }
}

validateProductionApiOrigin();

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
