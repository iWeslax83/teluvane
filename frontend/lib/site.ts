// frontend/lib/site.ts
export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const SITE_NAME = "TELUVANE";

export const FOUNDER = {
  name: "Emir Sakarya",
  linkedin: "https://www.linkedin.com/in/emirsakarya",
  github: "https://github.com/iWeslax83",
  stratos: "https://stratosiha.com",
};

export const ORG_SAME_AS = ["https://github.com/iWeslax83/teluvane"];
