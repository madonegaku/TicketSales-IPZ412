import assert from "assert";

describe("web", function () {
  it("package.json has correct name", async function () {
    const { name } = await import("../package.json");
    assert.strictEqual(name, "web");
  });
});
