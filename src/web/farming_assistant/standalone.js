import { mount } from "./index.js";

const app = document.getElementById("app");
const alerts = document.getElementById("alerts");

function notify(message, level = "info") {
  alerts.textContent = String(message);
  alerts.dataset.level = String(level);
}

async function query(operation, payload = {}) {
  if (operation !== "targets" && operation !== "preview") {
    throw new Error("Unsupported read-only operation");
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(payload)) {
    if (value !== null && value !== undefined) params.set(key, String(value));
  }
  const url = "/api/" + operation + "?" + params.toString();
  const response = await fetch(url, {
    method: "GET",
    credentials: "omit",
    cache: "no-store",
    headers: { Accept: "application/json" },
    redirect: "error"
  });
  if (!response.ok) {
    throw new Error("Read-only preview unavailable (HTTP " + response.status + ")");
  }
  return response.json();
}

const dispose = mount(app, {
  query,
  t: (value) => value,
  notify
});
window.addEventListener("pagehide", () => dispose(), { once: true });
