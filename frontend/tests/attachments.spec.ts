import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const photo = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGNkYPjPgA0wYRWlkwQAlocBCyQOisYAAAAASUVORK5CYII=",
  "base64",
);
const otherPhoto = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAEklEQVR4nGP8z4AdMOEQp4sEAJiFAQtsMIKbAAAAAElFTkSuQmCC",
  "base64",
);
const password = "Attachments-e2e-password-123!";

async function login(page: Page, email: string, secret: string) {
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(secret);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sair da conta" }),
  ).toBeVisible();
}

test("fotos com API real: envio, download, privacidade e remoção", async ({
  page,
}) => {
  await login(page, "e2e-admin@example.com", "E2E-only-password-123!");
  const cookies = await page.context().cookies();
  const headers = {
    Origin: "http://127.0.0.1:5190",
    "X-CSRF-Token": cookies.find((item) => item.name === "facilities_csrf")!
      .value,
  };
  async function post(path: string, data: object) {
    const response = await page.request.post("/api/v1" + path, {
      headers,
      data,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  const company = await post("/foundation/companies", {
    trade_name: "Piloto Fotos E2E",
    corporate_name: "Piloto Fotos E2E LTDA",
    slug: "fotose2e",
    cnpj: "11222333000181",
    contact_phone: "+5511999999999",
    address: "Rua de Testes",
    address_number: "100",
    address_complement: "",
    neighborhood: "Centro",
    city: "São Paulo",
    state: "SP",
    postal_code: "01001000",
    operational_profile: "office",
    admin: {
      full_name: "Administrador Fotos",
      email: "photos-owner-e2e@example.com",
      password,
    },
  });
  const unit = await post(`/foundation/companies/${company.id}/locations`, {
    name: "Unidade Fotos",
    kind: "unit",
    parent_id: null,
  });
  const base = `/operations/companies/${company.id}`;
  const category = await post(base + "/categories", { name: "Climatização" });
  const invited = await post(`/foundation/companies/${company.id}/users`, {
    name: "Solicitante Fotos",
    email: "photos-requester-e2e@example.com",
    roles: ["requester"],
    all_units: false,
    unit_ids: [unit.id],
  });
  const token = new URLSearchParams(
    new URL(invited.invitation.url).hash.substring(1),
  ).get("token");
  await post("/public/invitations/accept", { token, password });
  const occurrence = await post(base + "/occurrences", {
    title: "Vazamento para verificar",
    description: "Gotejamento no equipamento da recepção.",
    location_id: unit.id,
    category_id: category.id,
    requester_id: invited.user.id,
    client_request_id: crypto.randomUUID(),
  });
  const order = await post(base + "/orders", {
    occurrence_id: occurrence.id,
    expected_occurrence_version: occurrence.version,
    title: occurrence.title,
    description: occurrence.description,
    impact: 2,
    urgency: 2,
    assignee_id: null,
  });
  await page.goto(`/nexus/ordens?empresa=${company.id}&ordem=${order.id}`);
  const dialog = page.getByRole("dialog");
  const section = dialog.getByRole("region", { name: "Fotos de evidência" });
  await expect(section.getByLabel("Selecionar foto")).toBeVisible();
  await section.getByLabel("Selecionar foto").setInputFiles({
    name: "Evidência compartilhada.png",
    mimeType: "image/png",
    buffer: photo,
  });
  await section.getByRole("button", { name: "Enviar imagem" }).click();
  await expect(
    section.getByText("Evidência compartilhada.png", { exact: true }),
  ).toBeVisible();
  await section.getByLabel("Selecionar foto").setInputFiles({
    name: "Diagnóstico interno.png",
    mimeType: "image/png",
    buffer: otherPhoto,
  });
  await section
    .getByLabel("Quem pode acessar a imagem")
    .selectOption("internal");
  await section.getByRole("button", { name: "Enviar imagem" }).click();
  await expect(
    section.getByText("Diagnóstico interno.png", { exact: true }),
  ).toBeVisible();
  const privateList = await page.request.get(
    "/api/v1" + base + `/orders/${order.id}/attachments`,
  );
  const privateId = (await privateList.json()).items.find(
    (item: { visibility: string }) => item.visibility === "internal",
  ).id;
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await login(page, "photos-requester-e2e@example.com", password);
  await page.goto(`/app/ordens?empresa=${company.id}&ordem=${order.id}`);
  await expect(
    section.getByText("Evidência compartilhada.png", { exact: true }),
  ).toBeVisible();
  await expect(
    section.getByText("Diagnóstico interno.png", { exact: true }),
  ).toHaveCount(0);
  await expect(section.getByLabel("Quem pode acessar a imagem")).toHaveCount(0);
  expect(
    (
      await page.request.get(
        "/api/v1" + base + `/orders/${order.id}/attachments/${privateId}`,
      )
    ).status(),
  ).toBe(404);
  const download = page.waitForEvent("download");
  await section
    .getByRole("button", {
      name: "Baixar Evidência compartilhada.png",
      exact: true,
    })
    .click();
  expect((await download).suggestedFilename()).toBe(
    "Evidência compartilhada.png",
  );
  await page.keyboard.press("Escape");
  await page.goto(
    `/app/ocorrencias?empresa=${company.id}&ocorrencia=${occurrence.id}`,
  );
  await section.getByLabel("Selecionar foto").setInputFiles({
    name: "Foto do solicitante.png",
    mimeType: "image/png",
    buffer: photo,
  });
  await section.getByRole("button", { name: "Enviar imagem" }).click();
  await expect(
    section.getByText("Foto do solicitante.png", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await section
    .getByRole("button", {
      name: "Remover Foto do solicitante.png",
      exact: true,
    })
    .click();
  await expect(section.getByLabel("Motivo da remoção")).toHaveCount(0);
  await section.getByRole("button", { name: "Confirmar remoção" }).click();
  await expect(
    section.getByText("Foto do solicitante.png", { exact: true }),
  ).toHaveCount(0);
  await expect(section.getByRole("status")).toHaveText(
    "Imagem removida. A ação permanece na auditoria.",
  );
});
