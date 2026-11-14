import { test } from "@playwright/test";
import { resolveFromUi } from "./helpers";
test("reset, identity, one-click approval and resolved timeline against the isolated API", async ({ page, request }) => {
 await resolveFromUi(page, request);
});
