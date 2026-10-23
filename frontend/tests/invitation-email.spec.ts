import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("convite com API real, fila e provedor simulado, sem enviar e-mail externo", async ({
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
  await expect(
    page.getByRole("button", { name: "Sair da conta" }),
  ).toBeVisible();
  const cookies = await page.context().cookies();
  const headers = {
    Origin: "http://127.0.0.1:5190",
    "X-CSRF-Token": cookies.find((item) => item.name === "facilities_csrf")!
      .value,
  };
  const companyResponse = await page.request.post(
    "/api/v1/foundation/companies",
    {
      headers,
      data: {
        trade_name: "Empresa Convites E2E",
        corporate_name: "Empresa Convites E2E LTDA",
        slug: "convitese2e",
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
          full_name: "Administrador Convites",
          email: "email-owner-e2e@example.com",
          password: "Email-e2e-password-123!",
        },
      },
    },
  );
  expect(companyResponse.ok(), await companyResponse.text()).toBeTruthy();
  const company = await companyResponse.json();
  await page.goto("/nexus/configuracoes/integracoes");
  await page
    .getByLabel("API Key do Resend", { exact: true })
    .fill("resend-key-e2e-placeholder");
  await page
    .getByLabel("E-mail remetente", { exact: true })
    .fill("facilities@example.com");
  await page.getByLabel("Habilitar envio de convites por e-mail").check();
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(
    page.getByText("Configurações salvas com sucesso."),
  ).toBeVisible();
  await page.goto("/nexus/usuarios?empresa=" + company.id);
  await page
    .getByRole("button", { name: "Convidar usuário", exact: true })
    .click();
  await page.getByLabel("Nome completo").fill("Pessoa Convite E2E");
  await page
    .getByLabel("E-mail corporativo")
    .fill("queued-person-e2e@example.com");
  await page.getByLabel("Todas as unidades atuais e futuras").check();
  await page.getByLabel("Enviar convite por e-mail").check();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("button", { name: "Gerar convite", exact: true })
    .click();
  await expect(
    page.getByText("Convite registrado na fila de e-mail.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await expect
    .poll(async () => {
      const result = await page.request.get(
        `/api/v1/foundation/companies/${company.id}/users`,
      );
      const rows = await result.json();
      return rows.find(
        (item: { email: string }) =>
          item.email === "queued-person-e2e@example.com",
      )?.invitation_email?.status;
    })
    .toBe("accepted");
  await page.getByRole("button", { name: "Atualizar envios" }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: "queued-person-e2e@example.com" });
  await expect(
    row.getByText("Último e-mail: Aceito pelo Resend — entrega não confirmada"),
  ).toBeVisible();
  await row.getByRole("button", { name: "Novo convite", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Gerar novo convite", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Enviar convite por e-mail")).not.toBeChecked();
  await page.setViewportSize({ width: 390, height: 900 });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("button", { name: "Gerar novo convite", exact: true })
    .click();
  await expect(page.getByLabel("Link individual do convite")).toBeVisible();
  await expect(
    page.getByText("Convite registrado na fila de e-mail.", { exact: false }),
  ).toHaveCount(0);
  await expect(page.getByRole("dialog")).toBeVisible();
});
