import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const longName =
  "Equipamento de climatização e renovação de ar da unidade administrativa e centro de operações, manutenção preventiva e atendimento aos colaboradores e visitantes do bloco norte".slice(
    0,
    160,
  );
const longEmail =
  "administracao.operacional.facilities@" +
  "centro-de-operacoes-e-servicos-corporativos.".repeat(3) +
  "example.com";
const demo = {
  id: "asset",
  code: "AC-001",
  name: "Ar da recepção",
  unit_id: "unit",
  location_id: "unit",
  category: "Climatização",
  criticality: "high",
  status: "active",
  version: 1,
};
const worst = [
  {
    ...demo,
    name: longName,
    code: "HVAC-MATRIZ-ADMINISTRATIVO-ANDAR-10-00001".slice(0, 40),
  },
  { ...demo, id: "short", code: "AR-02", name: "Ar", category: "Ar" },
  {
    ...demo,
    id: "unicode",
    code: "AR-03",
    name: "Refrigeração — São João / Nguyễn / 東京 👩🏽‍🔧",
  },
];

async function stress(page: Page) {
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => {
      const controls = document.createElement("aside");
      controls.id = "ui-stress-controls";
      controls.setAttribute("aria-label", "Cenários de teste visual");
      Object.assign(controls.style, {
        position: "fixed",
        bottom: "8px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: "9999",
        display: "flex",
        maxWidth: "100%",
        overflow: "auto",
        background: "#eef2f5",
        borderRadius: "8px",
        padding: "4px",
      });
      for (const [key, label] of [
        ["demo", "Demo data"],
        ["worst", "Worst case"],
        ["empty", "Empty"],
        ["one", "One"],
        ["large", "1,000 rows"],
      ]) {
        const button = document.createElement("button");
        button.textContent = label;
        button.className = "button secondary compact";
        button.onclick = () => {
          const url = new URL(location.href);
          url.searchParams.set("ui-case", key);
          location.href = url.toString();
        };
        controls.append(button);
      }
      document.body.append(controls);
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const mode = new URL(page.url()).searchParams.get("ui-case") ?? "demo";
    const path = new URL(route.request().url()).pathname;
    const extreme = mode === "worst";
    const assets =
      mode === "empty"
        ? []
        : mode === "large"
          ? Array.from({ length: 1000 }, (_, i) => ({
              ...demo,
              id: "asset-" + i,
              code: "AC-" + i,
            }))
          : mode === "attack"
            ? [{ ...demo, name: '<img src=x onerror="alert(1)">' }]
            : extreme
              ? worst
              : [demo];
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        json: {
          id: "owner",
          role: "company_user",
          roles: ["company_admin"],
          company_id: "company",
          all_units: true,
          unit_ids: [],
          name: extreme ? "👩🏽‍🔧 Jo" : "Jo",
          email: extreme ? longEmail : "jo@example.com",
        },
      });
    if (path.endsWith("/foundation/companies"))
      return route.fulfill({
        json: [
          {
            id: "company",
            name: extreme
              ? "Centro de Operações e Serviços Compartilhados — São João e Região Metropolitana"
              : "Empresa piloto",
            is_active: true,
          },
        ],
      });
    if (path.endsWith("/metadata"))
      return route.fulfill({
        json: {
          assets,
          locations: [
            {
              id: "unit",
              unit_id: "unit",
              kind: "unit",
              parent_id: null,
              name: extreme
                ? "Unidade administrativa e centro de operações compartilhadas — atendimento, manutenção e apoio aos colaboradores"
                : "Matriz",
              is_active: true,
            },
          ],
          categories: [],
          people: [],
          can_coordinate: true,
          can_review: true,
          can_report: true,
        },
      });
    if (path.endsWith("/assets/labels/whatsapp"))
      return route.fulfill({ json: { phone: "5511999999999" } });
    return route.fulfill({ json: [] });
  });
}

for (const width of [320, 1440]) {
  test(`stress visual com dados reais e limites a ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    await stress(page);
    for (const mode of ["demo", "worst", "empty", "one", "large"]) {
      await page.goto("/app/ativos?ui-case=" + mode);
      if (mode === "empty")
        await expect(
          page.getByRole("heading", { name: "Nenhum registro disponível" }),
        ).toBeVisible();
      else
        await expect(page.locator("tbody tr")).toHaveCount(
          mode === "large" ? 1000 : mode === "worst" ? 3 : 1,
        );
      await page.screenshot({
        path: info.outputPath(mode + ".png"),
        fullPage: mode !== "large",
      });
      await info.attach(mode + "-geometry", {
        body: JSON.stringify(
          await page.evaluate(() => ({
            viewport: innerWidth,
            content: document.documentElement.scrollWidth,
            avatar: document.querySelector(".avatar")?.textContent,
          })),
        ),
        contentType: "application/json",
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
      if (mode === "worst") {
        await expect(page.locator(".avatar")).toHaveText("👩🏽‍🔧");
        expect((await new AxeBuilder({ page }).analyze()).violations).toEqual(
          [],
        );
        await page
          .getByRole("button", {
            name: "Editar ativo " + longName.trim(),
            exact: true,
          })
          .click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.screenshot({ path: info.outputPath("worst-dialog.png") });
        await page.getByRole("button", { name: "Fechar diálogo" }).click();
        if (width === 1440) {
          await page.evaluate(() => {
            document.body.style.zoom = "2";
          });
          await page.screenshot({
            path: info.outputPath("worst-zoom-200.png"),
          });
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          ).toBeTruthy();
        }
      }
    }
  });
}

test.describe("controles de toque", () => {
  test.use({
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 550 },
  });
  test("campos legíveis, fechar acessível e rolagem contida", async ({
    page,
  }, info) => {
    await stress(page);
    await page.goto("/app/ativos?ui-case=worst");
    await page
      .getByRole("button", {
        name: "Editar ativo " + longName.trim(),
        exact: true,
      })
      .click();
    const dialog = page.getByRole("dialog");
    expect(
      await dialog
        .getByLabel("Nome", { exact: true })
        .evaluate((element) => parseFloat(getComputedStyle(element).fontSize)),
    ).toBeGreaterThanOrEqual(16);
    expect(
      await dialog
        .getByLabel("Criticidade", { exact: true })
        .evaluate((element) => parseFloat(getComputedStyle(element).fontSize)),
    ).toBeGreaterThanOrEqual(16);
    const close = dialog.getByRole("button", { name: "Fechar diálogo" });
    expect((await close.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await dialog.evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    await expect(close).toBeInViewport();
    await page.screenshot({ path: info.outputPath("touch-dialog.png") });
    expect(
      await dialog.evaluate(
        (element) => getComputedStyle(element).overscrollBehaviorY,
      ),
    ).toBe("contain");
  });
});

test("conteúdo HTML recebido da API permanece texto, sem executar código", async ({
  page,
}) => {
  await stress(page);
  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs++;
    void dialog.dismiss();
  });
  await page.goto("/app/ativos?ui-case=attack");
  await expect(page.locator("tbody")).toContainText(
    '<img src=x onerror="alert(1)">',
  );
  await expect(page.locator('tbody img[src="x"]')).toHaveCount(0);
  expect(dialogs).toBe(0);
});
