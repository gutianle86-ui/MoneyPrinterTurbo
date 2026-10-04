import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import type { App } from "vue";
import { useStudio } from "../src/composables/useStudio";
import { projectFixture, statusFixture } from "./fixtures";
import FeedbackForm from "../src/dialogs/FeedbackForm.vue";
import GenerateDialog from "../src/dialogs/GenerateDialog.vue";
import CharactersPage from "../src/views/CharactersPage.vue";
import ExportCard from "../src/components/ExportCard.vue";
import ProductionPage from "../src/views/ProductionPage.vue";
import type { PublicationFeedback } from "../src/types";

const studio = useStudio();
let app: App | undefined;
afterEach(() => {
  app?.unmount();
  app = undefined;
  studio.stop();
  studio.closeDialog();
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});
function mount(component: Parameters<typeof createApp>[0], props = {}) {
  studio.state.project = projectFixture();
  studio.state.status = statusFixture();
  studio.state.requestPending = false;
  studio.state.loading = false;
  const host = document.createElement("div");
  document.body.append(host);
  app = createApp(component, props);
  app.mount(host);
  return host;
}
describe("migrated Vue workflows", () => {
  it("preserves paid confirmation on unchanged polls and revokes it when price changes", async () => {
    studio.state.generateMode = "seedance";
    studio.state.selectedShots = new Set(["shot-a"]);
    const host = mount(ProductionPage);
    const paid = host.querySelector<HTMLInputElement>(".budget-line input")!;
    paid.checked = true;
    paid.dispatchEvent(new Event("change"));
    await nextTick();
    studio.state.project = projectFixture();
    await nextTick();
    expect(paid.checked).toBe(true);
    studio.state.status!.settings.estimate_per_second = 1;
    await nextTick();
    expect(paid.checked).toBe(false);
  });
  it("preserves unsaved character edits through project polling", async () => {
    const host = mount(CharactersPage);
    const textarea = host.querySelector<HTMLTextAreaElement>("#appearance-0")!;
    textarea.value = "未保存的角色设定";
    textarea.dispatchEvent(new Event("input"));
    await nextTick();
    studio.state.project = projectFixture();
    await nextTick();
    expect(
      host.querySelector<HTMLTextAreaElement>("#appearance-0")?.value,
    ).toBe("未保存的角色设定");
  });
  it("saves unknown feedback as null while retaining an explicit zero", async () => {
    studio.state.project = projectFixture();
    // Set the export before mounting: the component captures its own form draft.
    const entry = {
      id: "export-a",
      kind: "production",
      duration: 6,
      created_at: "",
      file: "",
      subtitle: "",
      manifest: "",
    };
    const host = document.createElement("div");
    document.body.append(host);
    studio.state.project.exports = [entry];
    studio.state.status = statusFixture();
    studio.state.requestPending = false;
    studio.state.loading = false;
    const saved = vi
      .spyOn(studio.api, "feedback")
      .mockImplementation(async (_pid, _eid, feedback) => {
        expect(feedback.views).toBe(0);
        expect(feedback.revenue).toBeNull();
        return projectFixture();
      });
    app = createApp(FeedbackForm, { id: "export-a" });
    app.mount(host);
    const views = host.querySelector<HTMLInputElement>("#feedback-views")!;
    views.value = "0";
    views.dispatchEvent(new Event("input"));
    host
      .querySelector("form")!
      .dispatchEvent(new Event("submit", { cancelable: true }));
    for (let i = 0; i < 6; i++) await Promise.resolve();
    expect(saved).toHaveBeenCalledTimes(1);
  });
  it("disables a paid confirmation if its captured model or story changes", async () => {
    const host = mount(GenerateDialog, {
      options: {
        shot_ids: ["shot-a"],
        mode: "seedance",
        variants: 1,
        confirm_paid: true,
      },
      revision: "r1",
      model: "mini",
      rate: 0.6,
    });
    const button = [...host.querySelectorAll("button")].find((b) =>
      b.textContent?.includes("提交本次付费制作"),
    )!;
    expect(button.disabled).toBe(false);
    studio.state.project!.workflow_status.story_revision = "r2";
    await nextTick();
    expect(button.disabled).toBe(true);
  });
  it("does not fabricate profit or ROI from unknown costs", async () => {
    const feedback: PublicationFeedback = {
      platform: "平台",
      published_url: "",
      views: 0,
      likes: null,
      conversions: null,
      revenue: 10,
      actual_cost: null,
      notes: "",
    };
    const host = mount(ExportCard, {
      entry: {
        id: "e",
        kind: "production",
        duration: 6,
        created_at: "2026-10-04",
        file: "",
        subtitle: "",
        manifest: "",
        feedback,
      },
    });
    expect(host.textContent).toContain("播放 0");
    expect(host.textContent).not.toContain("利润");
    expect(host.textContent).not.toContain("成本回报率");
  });
});
