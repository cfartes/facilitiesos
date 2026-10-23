import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const width of [1440, 390]) {
  test(`login no modelo RotaFY acessível a ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({
        status: 401,
        json: { detail: "E-mail ou senha inválidos." },
      }),
    );
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Bem-vindo de volta" }),
    ).toBeVisible();
    await expect(
      page.getByText("PORTAL DA EMPRESA", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("E-mail", { exact: true }).fill("teste@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("Senha-de-teste-123!");
    await page
      .getByRole("button", { name: "Mostrar senha", exact: true })
      .focus();
    await page.keyboard.press("Enter");
    await expect(page.getByLabel("Senha", { exact: true })).toHaveAttribute(
      "type",
      "text",
    );
    await page
      .getByRole("button", { name: "Ocultar senha", exact: true })
      .click();
    await expect(page.getByLabel("Senha", { exact: true })).toHaveAttribute(
      "type",
      "password",
    );
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
    await expect(page.getByRole("alert")).toHaveText(
      "E-mail ou senha inválidos.",
    );
    await expect(page.getByLabel("E-mail", { exact: true })).toHaveValue(
      "teste@example.com",
    );
    await expect(page.getByLabel("Senha", { exact: true })).toHaveValue("");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("link", { name: "Administração Nexus", exact: true })
      .click();
    await expect(
      page.getByText("ADMINISTRAÇÃO DA PLATAFORMA", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Esqueci minha senha" }),
    ).toHaveCount(0);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({
      path: `test-results/login-nexus-${width}.png`,
      fullPage: true,
    });
  });
}
