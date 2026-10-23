import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const company = { id: "company-demo", name: "Empresa piloto", is_active: true };
const place = {
  id: "unit-demo",
  unit_id: "unit-demo",
  parent_id: null,
  kind: "unit",
  name: "Unidade Centro",
  is_active: true,
};
const category = {
  id: "category-demo",
  name: "Climatização",
  is_active: true,
  version: 1,
};
const person = {
  id: "person-demo",
  name: "Ana Técnica",
  roles: ["technician"],
  all_units: true,
  unit_ids: [],
};
const asset = {
  id: "asset-demo",
  unit_id: place.id,
  location_id: place.id,
  code: "AC-001",
  name: "Ar da recepção",
  category: "Climatização",
  criticality: "high",
  status: "active",
  version: 1,
};
const initialOrder = {
  id: "order-demo",
  code: "OS-00001",
  title: "Vazamento na recepção",
  description: "Água escorrendo do equipamento durante o funcionamento.",
  unit_id: place.id,
  location_id: place.id,
  location_name: place.name,
  category_id: category.id,
  category_name: category.name,
  asset_id: asset.id,
  asset_name: asset.name,
  assignee_id: person.id,
  assignee_name: person.name,
  state: "assigned",
  priority: "high",
  impact: 2,
  urgency: 4,
  cycle: 1,
  version: 1,
  solution: "",
  evidence: "",
  created_at: "2026-10-23T12:00:00Z",
  updated_at: "2026-10-23T12:00:00Z",
  resolved_at: null,
  closed_at: null,
};

async function mockOperations(page: Page, requester = false) {
  let order = { ...initialOrder };
  const messages: object[] = [];
  const writes: { path: string; body: any }[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (method !== "GET") {
      const body = route.request().postDataJSON();
      writes.push({ path, body });
      if (path.endsWith("/actions"))
        order = {
          ...order,
          state: body.action === "start" ? "in_progress" : "resolved",
          solution: body.solution,
          evidence: body.evidence,
          version: order.version + 1,
        };
      if (path.endsWith("/messages"))
        messages.push({
          id: "message-" + messages.length,
          ...body,
          actor_name: person.name,
          created_at: initialOrder.created_at,
        });
      return route.fulfill({ json: { message: "Registrado" } });
    }
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        json: {
          id: person.id,
          name: person.name,
          email: "demo@example.com",
          role: requester ? "company_user" : "superadmin",
          company_id: requester ? company.id : null,
          roles: requester ? ["requester"] : [],
          all_units: true,
          unit_ids: [],
        },
      });
    if (path.endsWith("/foundation/companies"))
      return route.fulfill({ json: [company] });
    if (path.endsWith("/metadata"))
      return route.fulfill({
        json: {
          locations: [place],
          categories: [category],
          assets: [asset],
          people: requester ? [] : [person],
          viewer_id: requester ? person.id : null,
          can_coordinate: !requester,
          can_review: !requester,
          can_report: true,
        },
      });
    if (path.endsWith("/orders/order-demo"))
      return route.fulfill({
        json: {
          order,
          occurrences: [],
          messages,
          events: [
            {
              id: "event-demo",
              actor_name: person.name,
              action: "order.created",
              note: "Atendimento iniciado na triagem.",
              visibility: "shared",
              cycle: 1,
              created_at: initialOrder.created_at,
            },
          ],
          can_coordinate: !requester,
          can_execute: !requester,
          can_internal: !requester,
          can_message: true,
        },
      });
    if (path.endsWith("/orders")) return route.fulfill({ json: [order] });
    if (path.endsWith("/attachments"))
      return route.fulfill({
        json: { items: [], can_upload: true, can_internal: !requester },
      });
    if (path.endsWith("/occurrences") || path.endsWith("/notifications"))
      return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: {} });
  });
  return writes;
}

for (const width of [1440, 390]) {
  test(`operação acessível e formulários a ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await mockOperations(page);
    for (const [path, title, button] of [
      ["categorias", "Categorias de serviço", "Nova categoria"],
      ["ativos", "Ativos", "Novo ativo"],
      ["ocorrencias", "Ocorrências", "Nova ocorrência"],
    ]) {
      await page.goto("/nexus/" + path);
      await expect(
        page.getByRole("heading", { name: title, exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: button, exact: true }),
      ).toBeEnabled();
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      await page.getByRole("button", { name: button, exact: true }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).not.toBeVisible();
      await expect(
        page.getByRole("button", { name: button, exact: true }),
      ).toBeFocused();
    }
    await page.goto("/nexus/ordens");
    await page.getByRole("button", { name: "Visualizar quadro" }).click();
    await expect(
      page.getByText(initialOrder.title, { exact: true }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}

test("execução e resolução preservam modal e enviam versão e evidência", async ({
  page,
}) => {
  const writes = await mockOperations(page);
  await page.goto("/nexus/ordens?ordem=order-demo");
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: initialOrder.title }),
  ).toBeVisible();
  await dialog.locator("#order-action").selectOption("start");
  await dialog
    .locator("form")
    .filter({ has: page.locator("#order-action") })
    .locator('button[type="submit"], button:not([type])')
    .last()
    .click();
  await expect(dialog.locator(".order-state")).toHaveText("Em execução");
  await dialog.locator("#order-action").selectOption("resolve");
  await dialog
    .locator("#resolution")
    .fill("Limpeza e desobstrução do dreno concluídas.");
  await dialog
    .locator("#evidence")
    .fill("Equipamento ligado por trinta minutos sem vazamentos.");
  await dialog
    .locator("form")
    .filter({ has: page.locator("#order-action") })
    .locator('button[type="submit"], button:not([type])')
    .last()
    .click();
  await expect(dialog.locator(".order-state")).toHaveText("Resolvida");
  expect(
    writes
      .filter((item) => item.path.endsWith("/actions"))
      .map((item) => item.body.expected_version),
  ).toEqual([1, 2]);
  expect(writes.at(-1)?.body.evidence).toContain("sem vazamentos");
  await expect(
    dialog.getByText("Equipamento ligado por trinta minutos sem vazamentos."),
  ).toBeVisible();
});

test("solicitante registra relato sem acesso às ações internas", async ({
  page,
}) => {
  const writes = await mockOperations(page, true);
  await page.goto("/app/ocorrencias");
  await page.getByRole("button", { name: "Nova ocorrência" }).click();
  await page.locator("#report-title").fill("Ar-condicionado com vazamento");
  await page.locator("#report-place").selectOption(place.id);
  await page.locator("#report-category").selectOption(category.id);
  await page.locator("#report-asset").selectOption(asset.id);
  await page
    .locator("#report-description")
    .fill("Água escorrendo continuamente sobre o piso da recepção.");
  await page.getByRole("button", { name: "Registrar ocorrência" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(writes[0].body.client_request_id).toMatch(/^[a-f0-9-]{36}$/);
  expect(writes[0].body.requester_id).toBeUndefined();
  await page.goto("/app/ordens?ordem=order-demo");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator("#order-action")).toHaveCount(0);
  await expect(page.locator("#detail-assignee")).toHaveCount(0);
  await expect(page.getByText("Nota interna", { exact: true })).toHaveCount(0);
});
