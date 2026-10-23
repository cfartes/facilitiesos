import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function mockApi(page: Page, configured = false) {
  let config = {
    version: configured ? 1 : 0,
    openwa_base_url: "https://openwa.187-77-58-10.sslip.io/api",
    openwa_key_configured: configured,
    resend_key_configured: configured,
    invitation_email_enabled: false,
    email_from: configured ? "sender@example.com" : "",
    updated_at: null as string | null,
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me") || path.endsWith("/auth/login"))
      return route.fulfill({
        json: { email: "admin@example.com", role: "superadmin" },
      });
    if (path.endsWith("/test/openwa"))
      return route.fulfill({
        json: {
          message: "Consulta de sessões concluída.",
          sessions: [
            { id: "session-id", name: "Unidade piloto", status: "READY" },
          ],
        },
      });
    if (path.endsWith("/test/resend"))
      return route.fulfill({
        json: {
          message: "Envio aceito pelo Resend. Confira a caixa de entrada.",
        },
      });
    if (path.endsWith("/nexus/integrations")) {
      if (route.request().method() === "PUT") {
        const data = route.request().postDataJSON();
        config = {
          ...config,
          version: config.version + 1,
          updated_at: "2026-10-23T12:00:00Z",
          email_from: data.email_from ?? config.email_from,
          invitation_email_enabled:
            !!data.invitation_email_enabled && !data.clear_resend_key,
          openwa_key_configured: data.clear_openwa_key
            ? false
            : !!data.openwa_api_key || config.openwa_key_configured,
          resend_key_configured: data.clear_resend_key
            ? false
            : !!data.resend_api_key || config.resend_key_configured,
        };
      }
      return route.fulfill({ json: config });
    }
    if (path.endsWith("/auth/logout")) return route.fulfill({ status: 204 });
    return route.fulfill({ status: 404, json: {} });
  });
}

test("configura as duas chaves, limpa os campos e testa provedores", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/nexus/configuracoes/integracoes");
  await expect(
    page.getByRole("heading", { name: "Integrações", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("API Key do OpenWA", { exact: true })
    .fill("owa_fake_secret_123");
  await page
    .getByLabel("API Key do Resend", { exact: true })
    .fill("re_fake_secret_456");
  await page
    .getByLabel("E-mail remetente", { exact: true })
    .fill("sender@example.com");
  await expect(
    page.getByRole("button", { name: "Consultar sessões OpenWA" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(
    page.getByText("Configurações salvas com sucesso."),
  ).toBeVisible();
  await expect(
    page.getByLabel("API Key do OpenWA", { exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByLabel("API Key do Resend", { exact: true }),
  ).toHaveValue("");
  await page.getByRole("button", { name: "Consultar sessões OpenWA" }).click();
  await expect(page.getByText("Unidade piloto")).toBeVisible();
  await page.getByLabel("Destinatário do teste").fill("recipient@example.com");
  await page
    .getByRole("button", { name: "Enviar e-mail de teste", exact: true })
    .click();
  await expect(
    page.getByText("Envio aceito pelo Resend. Confira a caixa de entrada."),
  ).toBeVisible();
});

test("remoção é explícita e só ocorre após salvar", async ({ page }) => {
  await mockApi(page, true);
  await page.goto("/nexus/configuracoes/integracoes");
  await page.getByLabel("Remover a chave OpenWA ao salvar").check();
  await expect(
    page.getByLabel("API Key do OpenWA", { exact: true }),
  ).toBeDisabled();
  await expect(page.getByText("Chave cadastrada", { exact: true })).toHaveCount(
    2,
  );
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(page.getByText("Não configurado", { exact: true })).toHaveCount(
    1,
  );
  await expect(page.getByText("Chave cadastrada", { exact: true })).toHaveCount(
    1,
  );
});

test("habilitação de convites é salva e remover a chave a desativa", async ({
  page,
}) => {
  await mockApi(page, true);
  await page.goto("/nexus/configuracoes/integracoes");
  const choice = page.getByLabel("Habilitar envio de convites por e-mail");
  await expect(choice).not.toBeChecked();
  await choice.check();
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(
    page.getByText("Configurações salvas com sucesso."),
  ).toBeVisible();
  await expect(choice).toBeChecked();
  await page.getByLabel("Remover a chave Resend ao salvar").check();
  await expect(choice).not.toBeChecked();
  await expect(choice).toBeDisabled();
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(
    page.getByText("Configurações salvas com sucesso."),
  ).toBeVisible();
  await expect(choice).not.toBeChecked();
});

test("erro de concorrência preserva alterações para revisão", async ({
  page,
}) => {
  await mockApi(page, true);
  await page.route("**/api/v1/nexus/integrations", async (route) => {
    if (route.request().method() === "PUT")
      return route.fulfill({
        status: 409,
        json: {
          detail:
            "Outra alteração foi salva. Recarregue as configurações antes de continuar.",
        },
      });
    return route.fallback();
  });
  await page.goto("/nexus/configuracoes/integracoes");
  await page
    .getByLabel("API Key do OpenWA", { exact: true })
    .fill("owa_new_fake_key");
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Outra alteração foi salva",
  );
  await expect(
    page.getByLabel("API Key do OpenWA", { exact: true }),
  ).toHaveValue("owa_new_fake_key");
});

test("falha de provedor é exibida e permite nova tentativa", async ({
  page,
}) => {
  await mockApi(page, true);
  await page.route("**/api/v1/nexus/integrations/test/openwa", (route) =>
    route.fulfill({
      status: 502,
      json: { detail: "O provedor recusou a API Key." },
    }),
  );
  await page.goto("/nexus/configuracoes/integracoes");
  await page.getByRole("button", { name: "Consultar sessões OpenWA" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "O provedor recusou a API Key.",
  );
  await expect(
    page.getByRole("button", { name: "Consultar sessões OpenWA" }),
  ).toBeEnabled();
});

test("login e logout sem armazenar credenciais no navegador", async ({
  page,
}) => {
  let loggedIn = false;
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        status: 401,
        json: { detail: "Entre novamente." },
      });
    if (path.endsWith("/auth/login")) {
      loggedIn = true;
      return route.fulfill({
        json: { email: "admin@example.com", role: "superadmin" },
      });
    }
    if (path.endsWith("/auth/logout")) {
      loggedIn = false;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({
      json: {
        version: 0,
        openwa_base_url: "https://openwa.187-77-58-10.sslip.io/api",
        openwa_key_configured: false,
        resend_key_configured: false,
        email_from: "",
        updated_at: null,
      },
    });
  });
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill("admin@example.com");
  await page.getByLabel("Senha", { exact: true }).fill("fake-password-123");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Integrações", exact: true }),
  ).toBeVisible();
  expect(loggedIn).toBe(true);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("heading", { name: "Acesse o Facilities OS" }),
  ).toBeVisible();
  expect(loggedIn).toBe(false);
});

for (const width of [1440, 390]) {
  test(`acessibilidade e layout em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockApi(page, true);
    await page.goto("/nexus/configuracoes/integracoes");
    await expect(
      page.getByRole("heading", { name: "Integrações", exact: true }),
    ).toBeVisible();
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
      path: `test-results/integrations-${width}.png`,
      fullPage: true,
    });
  });
}

test("campos e controles são acessíveis pelo teclado", async ({ page }) => {
  await mockApi(page);
  await page.goto("/nexus/configuracoes/integracoes");
  await expect(
    page.getByRole("heading", { name: "Integrações", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Pular para o conteúdo" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByLabel("API Key do OpenWA", { exact: true }),
  ).toBeFocused();
  await page.keyboard.type("owa_fake_keyboard_key");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Mostrar API Key do OpenWA" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByLabel("API Key do OpenWA", { exact: true }),
  ).toHaveAttribute("type", "text");
});
