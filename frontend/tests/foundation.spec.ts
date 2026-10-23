import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const companyId = "d1591d4b-5aac-4ff2-bf86-644cc225b942";
const unitId = "58991d4b-5aac-4ff2-bf86-644cc225b943";
const memberId = "58991d4b-5aac-4ff2-bf86-644cc225b944";
const company = {
  id: companyId,
  name: "Empresa de demonstração",
  slug: "demonstracao",
  is_active: true,
  version: 1,
  created_at: "2026-10-23T12:00:00Z",
};
const unit = {
  id: unitId,
  company_id: companyId,
  unit_id: unitId,
  parent_id: null,
  kind: "unit",
  name: "Unidade de demonstração",
  criticality: "medium",
  timezone: "America/Sao_Paulo",
  is_active: true,
  version: 1,
};
const invitation = {
  url: "http://127.0.0.1:5180/convite#token=demonstration-token-with-no-real-access-1234567890",
  expires_in_hours: 48,
};

async function mockFoundation(
  page: Page,
  scope: "superadmin" | "requester" = "superadmin",
) {
  const members = [
    {
      id: memberId,
      company_id: companyId,
      name: "Pessoa de demonstração",
      email: "pessoa@example.com",
      roles: ["requester"],
      unit_ids: [unitId],
      all_units: false,
      is_active: true,
      version: 1,
      invitation_pending: true,
    },
  ];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        json: {
          email: "admin@example.com",
          name: "Pessoa de demonstração",
          role: scope === "superadmin" ? "superadmin" : "company_user",
          company_id: scope === "superadmin" ? null : companyId,
          roles: scope === "superadmin" ? [] : ["requester"],
          unit_ids: [unitId],
          all_units: scope === "superadmin",
        },
      });
    if (path.endsWith("/foundation/companies"))
      return route.fulfill({
        json: route.request().method() === "GET" ? [company] : company,
      });
    if (path.endsWith("/locations")) return route.fulfill({ json: [unit] });
    if (path.endsWith("/users"))
      return route.fulfill({
        json:
          route.request().method() === "GET"
            ? members
            : { user: members[0], invitation },
      });
    if (path.endsWith("/audit"))
      return route.fulfill({
        json: [
          {
            id: 1,
            actor: "admin@example.com",
            action: "company.created",
            entity_id: companyId,
            created_at: "2026-10-23T12:00:00Z",
          },
        ],
      });
    if (path.endsWith("/public/invitations/accept"))
      return route.fulfill({
        json: {
          message:
            "Acesso ativado. Entre com o e-mail do convite e sua nova senha.",
        },
      });
    return route.fulfill({ status: 404, json: {} });
  });
}

test("cadastro de empresa, validação e diálogo por teclado", async ({
  page,
}) => {
  await mockFoundation(page);
  await page.goto("/nexus/empresas");
  await expect(page.getByRole("heading", { name: company.name })).toBeVisible();
  await page.getByRole("button", { name: "Nova empresa" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Nome da empresa")).toBeFocused();
  await page.getByLabel("Nome da empresa").fill("Nova Empresa");
  await page.getByLabel("Identificador", { exact: true }).fill("nova-empresa");
  const submission = page.waitForRequest(
    (request) =>
      request.url().endsWith("/foundation/companies") &&
      request.method() === "POST",
  );
  await page.getByRole("button", { name: "Salvar empresa" }).click();
  expect((await submission).postDataJSON()).toEqual({
    name: "Nova Empresa",
    slug: "nova-empresa",
  });
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Nova empresa" }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Nova empresa" }),
  ).toBeFocused();
});

test("convite com escopo de unidade sem persistir o token", async ({
  page,
}) => {
  await mockFoundation(page);
  await page.goto("/nexus/usuarios");
  await page
    .getByRole("button", { name: "Convidar usuário", exact: true })
    .click();
  await page.getByLabel("Nome completo").fill("Nova Pessoa");
  await page.getByLabel("E-mail corporativo").fill("nova@example.com");
  await page.getByLabel(unit.name, { exact: true }).check();
  await page.getByRole("button", { name: "Gerar convite" }).click();
  await expect(
    page.getByRole("heading", { name: "Convite de primeiro acesso" }),
  ).toBeVisible();
  await expect(page.getByLabel("Link individual do convite")).toHaveValue(
    invitation.url,
  );
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await expect(page.getByLabel("Link individual do convite")).toHaveCount(0);
});

test("solicitante vê apenas navegação autorizada", async ({ page }) => {
  await mockFoundation(page, "requester");
  await page.goto("/app/locais");
  await expect(
    page.getByRole("heading", { name: "Estrutura física" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Integrações", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Usuários e permissões", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Novo local" })).toHaveCount(0);
  await page.goto("/app/usuarios");
  await expect(page.getByRole("alert")).toContainText(
    "Seu perfil não permite acessar esta página.",
  );
});

test("aceite de convite remove token da URL e verifica confirmação de senha", async ({
  page,
}) => {
  await mockFoundation(page);
  await page.goto(invitation.url);
  await expect(
    page.getByRole("heading", { name: "Bem-vindo à sua operação" }),
  ).toBeVisible();
  expect(page.url()).toBe("http://127.0.0.1:5180/convite");
  await page
    .getByLabel("Nova senha", { exact: true })
    .fill("New-password-123!");
  await page.getByLabel("Confirme a senha").fill("Other-password-123!");
  await page.getByRole("button", { name: "Ativar meu acesso" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "As senhas precisam ser iguais.",
  );
  await page.getByLabel("Confirme a senha").fill("New-password-123!");
  await page.getByRole("button", { name: "Ativar meu acesso" }).click();
  await expect(
    page.getByRole("link", { name: "Ir para o login" }),
  ).toBeVisible();
});

for (const width of [1440, 390]) {
  for (const path of ["empresas", "locais", "usuarios", "auditoria"]) {
    test(`WCAG e responsividade de ${path} em ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      await mockFoundation(page);
      await page.goto(`/nexus/${path}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Carregando…", { exact: true })).toHaveCount(
        0,
      );
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/${path}-${width}.png`,
        fullPage: true,
      });
    });
  }
}

test("WCAG do diálogo de permissões e do primeiro acesso", async ({ page }) => {
  await mockFoundation(page);
  await page.goto("/nexus/usuarios");
  await page
    .getByRole("button", { name: "Convidar usuário", exact: true })
    .click();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.goto(invitation.url);
  await expect(
    page.getByRole("heading", { name: "Bem-vindo à sua operação" }),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("fluxo completo com API real: empresa, unidades, convite, login e escopo", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill("e2e-admin@example.com");
  await page
    .getByLabel("Senha", { exact: true })
    .fill("E2E-only-password-123!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page.getByRole("link", { name: "Empresas", exact: true }).click();
  await page.getByRole("button", { name: "Nova empresa" }).click();
  await page.getByLabel("Nome da empresa").fill("Empresa Piloto E2E");
  await page.getByLabel("Identificador", { exact: true }).fill("piloto-e2e");
  await page.getByRole("button", { name: "Salvar empresa" }).click();
  await expect(
    page.getByRole("heading", { name: "Empresa Piloto E2E" }),
  ).toBeVisible();
  await page
    .getByRole("main")
    .getByRole("link", { name: "Estrutura física", exact: true })
    .click();
  for (const name of ["Unidade Permitida E2E", "Unidade Restrita E2E"]) {
    await page.getByRole("button", { name: "Novo local" }).click();
    await page.getByLabel("Nome do local").fill(name);
    await page.getByRole("button", { name: "Salvar local" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(
      page.getByRole("cell", { name: new RegExp(name) }).first(),
    ).toBeVisible();
  }
  await page
    .getByRole("link", { name: "Usuários e permissões", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Convidar usuário", exact: true })
    .click();
  await page.getByLabel("Nome completo").fill("Solicitante E2E");
  await page.getByLabel("E-mail corporativo").fill("e2e-requester@example.com");
  await page.getByLabel("Unidade Permitida E2E", { exact: true }).check();
  await page.getByRole("button", { name: "Gerar convite" }).click();
  const url = await page.getByLabel("Link individual do convite").inputValue();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await page.goto(url);
  await page
    .getByLabel("Nova senha", { exact: true })
    .fill("Requester-password-123!");
  await page.getByLabel("Confirme a senha").fill("Requester-password-123!");
  await page.getByRole("button", { name: "Ativar meu acesso" }).click();
  await page.getByRole("link", { name: "Ir para o login" }).click();
  await page
    .getByLabel("E-mail", { exact: true })
    .fill("e2e-requester@example.com");
  await page
    .getByLabel("Senha", { exact: true })
    .fill("Requester-password-123!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Estrutura física" }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: /Unidade Permitida E2E/ }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Unidade Restrita E2E", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Integrações", exact: true }),
  ).toHaveCount(0);
});
