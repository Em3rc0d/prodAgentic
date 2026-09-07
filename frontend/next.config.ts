import type { NextConfig } from "next";

function isPrivateIpv4(hostname: string): boolean {
  const parts = hostname.split(".");
  if (parts.length !== 4) return false;

  const octets = parts.map((part) => Number(part));
  if (octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) {
    return false;
  }

  const [first, second] = octets;
  return (
    first === 10 ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

function validateProductionApiOrigin() {
  if (process.env.NODE_ENV !== "production") return;

  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is required for production builds. Refusing to compile a release that would fall back to localhost:8000."
    );
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
  const privateHttpExplicitlyAllowed =
    process.env.PRODAGENTIC_ALLOW_PRIVATE_HTTP_API === "true" &&
    parsed.protocol === "http:" &&
    isPrivateIpv4(parsed.hostname);

  if (!loopback && parsed.protocol !== "https:" && !privateHttpExplicitlyAllowed) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must use HTTPS for non-local production origins. RFC1918 HTTP is allowed only when PRODAGENTIC_ALLOW_PRIVATE_HTTP_API=true for an explicit local build."
    );
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

const nextConfig: NextConfig = {};

export default nextConfig;
