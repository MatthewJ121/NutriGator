import { test } from "node:test";
import assert from "node:assert/strict";
import { getLocalUserId } from "./userId.js";

test("matches the user IDs the backend makes with uuid5", async () => {
  assert.equal(await getLocalUserId("example-better-auth-user"), "6d327c13-a8cd-58e9-9cd1-c52a4627a846");
  assert.equal(await getLocalUserId("dc42fa70-09a7-4038-a3bb-f61dda854910"), "3f5e9363-895b-5fb4-8c02-1fa5d2d92c02");
  assert.equal(await getLocalUserId("abc"), "4cb200b3-be2f-5fc1-b242-dee8fee9e5cf");
});
