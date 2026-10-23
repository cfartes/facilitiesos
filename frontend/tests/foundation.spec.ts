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
  corporate_name: "Empresa de demonstração LTDA",
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
  url: "http://127.0.0.1:5190/convite#token=demonstration-token-with-no-real-access-1234567890",
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
    if (path.includes("/foundation/postal-code/"))
      return route.fulfill({
        json: {
          address: "Rua de Testes",
          neighborhood: "Centro",
          city: "São Paulo",
          state: "SP",
        },
      });
    if (path === `/api/v1/foundation/companies/${companyId}`)
      return route.fulfill({
        json: { ...company, ...route.request().postDataJSON() },
      });
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

async function fillCompany(page: Page, name: string, slug: string) {
  await page.getByLabel("Nome comercial", { exact: true }).fill(name);
  await page.getByLabel("Razão social", { exact: true }).fill(name + " LTDA");
  await page.getByLabel("Identificador de acesso", { exact: true }).fill(slug);
  await page.getByLabel("CPF/CNPJ", { exact: true }).fill("11222333000181");
  await page
    .getByLabel("Telefone / WhatsApp", { exact: true })
    .fill("11999999999");
  await page.getByLabel("CEP", { exact: true }).fill("01001000");
  await page.getByLabel("Endereço", { exact: true }).fill("Rua de Testes");
  await page.getByLabel("Número", { exact: true }).fill("100");
  await page.getByLabel("Bairro", { exact: true }).fill("Centro");
  await page.getByLabel("Cidade", { exact: true }).fill("São Paulo");
  await page.getByLabel("UF", { exact: true }).selectOption("SP");
  await page
    .getByLabel("Perfil operacional", { exact: true })
    .selectOption("office");
  await page
    .getByLabel("Nome completo", { exact: true })
    .fill("Administrador Inicial");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`owner${slug}@example.com`);
  await page
    .getByLabel("Senha inicial", { exact: true })
    .fill("Admin-test-password-123!");
}

test("edição mantém dados completos e não altera o administrador inicial", async ({
  page,
}) => {
  await mockFoundation(page);
  await page.goto("/nexus/empresas");
  await page.getByRole("button", { name: `Editar ${company.name}` }).click();
  await expect(page.getByLabel("Nome comercial")).toHaveValue(company.name);
  await expect(page.getByLabel("Razão social")).toHaveValue(
    company.corporate_name,
  );
  await expect(page.getByLabel("CPF/CNPJ", { exact: true })).toHaveValue(
    "11.222.333/0001-81",
  );
  await expect(page.getByLabel("CEP", { exact: true })).toHaveValue(
    "01001-000",
  );
  await expect(page.getByLabel("Senha inicial", { exact: true })).toHaveCount(
    0,
  );
  await page.getByLabel("Complemento (opcional)").fill("Sala 02");
  const submission = page.waitForRequest(
    (request) =>
      request.method() === "PUT" && request.url().endsWith(companyId),
  );
  await page
    .getByRole("button", { name: "Salvar empresa", exact: true })
    .click();
  const data = (await submission).postDataJSON();
  expect(data.address_complement).toBe("Sala 02");
  expect(data.admin).toBeUndefined();
  expect(data.plan_id).toBeUndefined();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("consulta de CEP preserva alterações manuais feitas durante a consulta", async ({
  page,
}) => {
  await mockFoundation(page);
  await page.route("**/foundation/postal-code/**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({
      json: {
        address: "Rua preenchida pelo CEP",
        neighborhood: "Centro",
        city: "Cidade do CEP",
        state: "SP",
      },
    });
  });
  await page.goto("/nexus/empresas");
  await page.getByRole("button", { name: "Nova empresa" }).click();
  const lookup = page.waitForRequest((request) =>
    request.url().includes("/foundation/postal-code/"),
  );
  await page.getByLabel("CEP", { exact: true }).fill("01001000");
  await lookup;
  await page
    .getByLabel("Cidade", { exact: true })
    .fill("Cidade informada manualmente");
  await expect(
    page.getByText(
      "CEP consultado. Confira o endereço e informe o número e o complemento, se houver.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Cidade", { exact: true })).toHaveValue(
    "Cidade informada manualmente",
  );
  await expect(page.getByLabel("Endereço", { exact: true })).toHaveValue(
    "Rua preenchida pelo CEP",
  );
});

test("falha de CEP permite cadastro com endereço manual", async ({ page }) => {
  await mockFoundation(page);
  await page.route("**/foundation/postal-code/**", (route) =>
    route.fulfill({ status: 502, json: { detail: "Serviço indisponível" } }),
  );
  await page.goto("/nexus/empresas");
  await page.getByRole("button", { name: "Nova empresa" }).click();
  await fillCompany(page, "Empresa Manual", "empresamanual");
  await expect(
    page.getByText(
      "Não foi possível consultar o CEP. Os campos continuam disponíveis para preenchimento manual.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cadastrar empresa" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

for (const width of [1440, 390]) {
  test(`cadastro completo acessível em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockFoundation(page);
    await page.goto("/nexus/empresas");
    await page.getByRole("button", { name: "Nova empresa" }).click();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/company-form-${width}.png`,
      fullPage: true,
    });
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
  await expect(page.getByLabel("Nome comercial")).toBeFocused();
  await fillCompany(page, "Nova Empresa", "novaempresa");
  await expect(page.getByLabel(/plano/i)).toHaveCount(0);
  const submission = page.waitForRequest(
    (request) =>
      request.url().endsWith("/foundation/companies") &&
      request.method() === "POST",
  );
  await page.getByRole("button", { name: "Cadastrar empresa" }).click();
  expect((await submission).postDataJSON()).toMatchObject({
    trade_name: "Nova Empresa",
    corporate_name: "Nova Empresa LTDA",
    slug: "novaempresa",
    cnpj: "11.222.333/0001-81",
    postal_code: "01001-000",
    admin: {
      full_name: "Administrador Inicial",
      email: "ownernovaempresa@example.com",
    },
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
  expect(page.url()).toBe("http://127.0.0.1:5190/convite");
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
  await page.route("**/api/v1/foundation/postal-code/**", (route) =>
    route.fulfill({
      json: {
        address: "Rua de Testes",
        neighborhood: "Centro",
        city: "São Paulo",
        state: "SP",
      },
    }),
  );
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
  await fillCompany(page, "Empresa Piloto E2E", "pilotoe2e");
  await page.getByRole("button", { name: "Cadastrar empresa" }).click();
  await expect(
    page.getByRole("heading", { name: "Empresa Piloto E2E" }),
  ).toBeVisible();
  await page
    .locator(".company-card")
    .filter({
      has: page.getByRole("heading", {
        name: "Empresa Piloto E2E",
        exact: true,
      }),
    })
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
