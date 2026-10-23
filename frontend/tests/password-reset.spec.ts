import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const width of [1440, 390]) {
  test(`recuperação e redefinição acessíveis a ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 960 });
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, json: { detail: "Entre novamente." } }),
    );
    await page.route("**/api/v1/public/password-reset/request", (route) =>
      route.fulfill({
        status: 202,
        json: {
          message:
            "Se houver uma conta elegível, você receberá um link de recuperação.",
        },
      }),
    );
    await page.goto("/recuperar-senha");
    await expect(
      page.getByRole("heading", { name: "Esqueceu sua senha?" }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.getByLabel("E-mail do acesso").fill("unknown@example.com");
    await page
      .getByRole("button", { name: "Solicitar recuperação", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText(
      "Se houver uma conta elegível",
    );
    await page.goto(
      "/redefinir-senha#token=synthetic-no-access-token-with-more-than-32-characters",
    );
    await expect(page).toHaveURL("/redefinir-senha");
    await expect(
      page.getByRole("heading", { name: "Defina uma nova senha" }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page
      .getByLabel("Nova senha", { exact: true })
      .fill("Changed-password-123!");
    await page.getByLabel("Confirme a senha").fill("Different-password-123!");
    await page
      .getByRole("button", { name: "Alterar senha", exact: true })
      .click();
    await expect(page.getByRole("alert")).toHaveText(
      "As senhas precisam ser iguais.",
    );
    await page.route("**/api/v1/public/password-reset/confirm", (route) =>
      route.fulfill({
        status: 400,
        json: { detail: "Link inválido, expirado ou já utilizado." },
      }),
    );
    await page.getByLabel("Confirme a senha").fill("Changed-password-123!");
    await page
      .getByRole("button", { name: "Alterar senha", exact: true })
      .click();
    await expect(page.getByRole("alert")).toHaveText(
      "Link inválido, expirado ou já utilizado.",
    );
    await page.goto("/redefinir-senha");
    await expect(page.getByRole("alert")).toContainText(
      "O link de recuperação está incompleto",
    );
    await expect(
      page.getByRole("button", { name: "Alterar senha", exact: true }),
    ).toHaveCount(0);
  });
}
