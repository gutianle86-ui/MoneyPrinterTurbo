import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { api } from "../src/api";
import { useStudio } from "../src/composables/useStudio";
import { projectFixture, statusFixture } from "./fixtures";

vi.mock("../src/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../src/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      status: vi.fn(),
      projects: vi.fn(),
      project: vi.fn(),
      generate: vi.fn(),
    },
  };
});
const studio = useStudio();
beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  studio.stop();
  Object.assign(studio.state, {
    project: null,
    projects: [],
    status: null,
    requestPending: false,
    selectedShots: new Set(),
    batchShots: new Set(),
    stage: 0,
  });
  vi.mocked(api.status).mockResolvedValue(statusFixture());
  vi.mocked(api.projects).mockResolvedValue([
    {
      id: "project-a",
      title: "测试项目",
      created_at: "",
      updated_at: "",
      budget: 100,
      reserved_cost: 7.2,
      shots: 1,
      exports: 0,
    },
  ]);
  vi.mocked(api.project).mockResolvedValue(projectFixture());
});
afterEach(() => {
  studio.stop();
  studio.closeDialog();
  vi.useRealTimers();
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
describe("Vue production state", () => {
  it("does not apply a delayed poll over a newer edit", async () => {
    await studio.init();
    const old = deferred<ReturnType<typeof projectFixture>>();
    vi.mocked(api.project).mockReturnValueOnce(old.promise);
    const polling = studio.poll();
    for (let i = 0; i < 6; i++) await Promise.resolve();
    const updated = projectFixture();
    updated.title = "刚保存的新标题";
    expect(await studio.act(async () => updated)).toBe(true);
    old.resolve(projectFixture());
    await polling;
    expect(studio.state.project?.title).toBe("刚保存的新标题");
  });
  it("blocks duplicate submissions while a request is pending", async () => {
    await studio.init();
    const pending = deferred<ReturnType<typeof projectFixture>>();
    const submit = vi.fn(() => pending.promise);
    const first = studio.act(submit);
    expect(await studio.act(submit)).toBe(false);
    expect(submit).toHaveBeenCalledTimes(1);
    pending.resolve(projectFixture());
    await first;
    expect(studio.state.requestPending).toBe(false);
  });
  it("keeps the last user-selected project when responses arrive out of order", async () => {
    const old = deferred<ReturnType<typeof projectFixture>>();
    vi.mocked(api.project)
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(projectFixture("project-b"));
    const first = studio.openProject("project-a");
    await studio.openProject("project-b");
    old.resolve(projectFixture("project-a"));
    await first;
    expect(studio.state.project?.id).toBe("project-b");
  });
  it("refuses a dialog write after its project has changed", async () => {
    await studio.init();
    studio.openDialog({ kind: "brief" });
    studio.state.project = projectFixture("project-b");
    const submit = vi.fn(async () => projectFixture());
    expect(await studio.act(submit)).toBe(false);
    expect(submit).not.toHaveBeenCalled();
    expect(studio.dialog.value).toBeNull();
    await nextTick();
  });
});
