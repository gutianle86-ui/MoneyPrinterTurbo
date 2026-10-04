import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, request } from "../src/api";

afterEach(() => vi.unstubAllGlobals());
describe("typed workbench API", () => {
  it("sends one paid request and never retries ambiguous submission failures", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("connection closed"));
    vi.stubGlobal("fetch", fetch);
    await expect(
      api.generate("p", {
        shot_ids: ["s"],
        mode: "seedance",
        variants: 1,
        confirm_paid: true,
      }),
    ).rejects.toThrow("connection closed");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].headers).toEqual({
      "X-Drama-Client": "1",
      "Content-Type": "application/json",
    });
  });
  it("uses multipart boundaries from the browser when uploading", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    const file = new File(["image"], "image.png", { type: "image/png" });
    await api.uploadShot("p", "s", "visual", file);
    expect(fetch.mock.calls[0][1].headers).toEqual({ "X-Drama-Client": "1" });
    expect(fetch.mock.calls[0][1].body).toBeInstanceOf(FormData);
  });
  it("preserves an existing corrected subtitle when choosing from comparison", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await api.selectCandidate("p", "s", "c");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      candidate_id: "c",
    });
  });
  it("retains HTTP status for project-removal recovery", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: "项目不存在" }), {
            status: 404,
          }),
        ),
    );
    await expect(request("/api/projects/p")).rejects.toEqual(
      new ApiError("项目不存在", 404),
    );
  });
});
