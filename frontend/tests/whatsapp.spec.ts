import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const qr =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGNkYPjPgA0wYRWlkwQAlocBCyQOisYAAAAASUVORK5CYII=";

for (const width of [1440, 390]) {
  test(`admin conecta WhatsApp com QR e acessibilidade a ${width}px`, async ({
    page,
  }) => {
    let started = false;
    let ready = false;
    let intakeEnabled = false;
    await page.setViewportSize({ width, height: 960 });
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/auth/me"))
        return route.fulfill({
          json: {
            role: "company_user",
            roles: ["company_admin"],
            name: "Admin Cliente",
            email: "admin-cliente@example.com",
            company_id: "demo",
          },
        });
      if (path.endsWith("/company/whatsapp/intake")) {
        if (route.request().method() === "POST")
          intakeEnabled = route.request().postDataJSON().enabled;
        return route.fulfill({
          json: {
            enabled: intakeEnabled,
            hook_status: intakeEnabled ? "active" : "disabled",
            public_url_configured: true,
            replies: intakeEnabled ? { uncertain: 1 } : {},
          },
        });
      }
      if (path.endsWith("/company/whatsapp/connect")) {
        started = true;
        return route.fulfill({
          json: { configured: true, status: "qr_ready", qr_code: qr },
        });
      }
      if (path.endsWith("/company/whatsapp"))
        return route.fulfill({
          json: {
            configured: true,
            status: ready ? "connected" : "not_connected",
            qr_code: null,
          },
        });
      return route.fulfill({ status: 404, json: {} });
    });
    await page.goto("/app/whatsapp");
    await expect(
      page.getByRole("link", { name: "WhatsApp", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Conectar WhatsApp", exact: true })
      .click();
    expect(started).toBe(true);
    await expect(
      page.getByRole("img", {
        name: "QR Code para conectar o WhatsApp da empresa",
      }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    ready = true;
    await page
      .getByRole("button", { name: "Atualizar conexão", exact: true })
      .click();
    await expect(
      page.getByText("WhatsApp conectado", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("img")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Conectar WhatsApp" }),
    ).toHaveCount(0);
    await page
      .getByRole("button", {
        name: "Ativar solicitações pelo WhatsApp",
        exact: true,
      })
      .click();
    await expect(
      page.getByText("Recebimento habilitado", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("alert")).toContainText(
      "respostas cujo envio não foi confirmado",
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page
      .getByRole("button", { name: "Desativar solicitações", exact: true })
      .click();
    await expect(
      page.getByText("Recebimento desativado", { exact: true }),
    ).toBeVisible();
  });
}

test("Superadmin tem somente empresas, integrações e auditoria e bloqueia acesso direto", async ({
  page,
}) => {
  let operationalCalls = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        json: {
          role: "superadmin",
          roles: [],
          name: "Nexus",
          email: "nexus@example.com",
        },
      });
    if (path.includes("/operations/") || path.endsWith("/company/whatsapp"))
      operationalCalls++;
    return route.fulfill({ json: [] });
  });
  await page.goto("/nexus/empresas");
  await expect(page.locator("nav a")).toHaveText([
    "Empresas",
    "Auditoria",
    "Integrações",
  ]);
  for (const path of [
    "/nexus/ordens",
    "/nexus/usuarios",
    "/nexus/locais",
    "/app/whatsapp",
  ]) {
    await page.goto(path);
    await expect(
      page.getByText("Seu perfil não permite acessar esta página."),
    ).toBeVisible();
  }
  expect(operationalCalls).toBe(0);
});

test("solicitante não acessa conexão WhatsApp", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) =>
    route.fulfill({
      json: {
        role: "company_user",
        roles: ["requester"],
        name: "Solicitante",
        company_id: "demo",
      },
    }),
  );
  await page.goto("/app/whatsapp");
  await expect(
    page.getByText("Seu perfil não permite acessar esta página."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "WhatsApp", exact: true }),
  ).toHaveCount(0);
});
