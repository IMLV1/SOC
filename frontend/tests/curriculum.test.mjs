import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { selectTrainingStep, trainingLink } from "../src/lib/curriculum.ts";

const curriculum = JSON.parse(await readFile(new URL("../public/learning/curriculum-v1.json", import.meta.url), "utf8"));
const practice = JSON.parse(await readFile(new URL("../public/learning/practice-v1.json", import.meta.url), "utf8"));

test("public training curriculum contains all three levels and 45 authored steps", () => {
  assert.equal(curriculum.purpose, "training");
  assert.equal(curriculum.content_status, "draft_for_testing");
  assert.deepEqual(curriculum.levels.map((level) => level.ordinal), [1, 2, 3]);
  const lessons = curriculum.levels.flatMap((level) => level.lessons);
  assert.equal(lessons.length, 9);
  assert.equal(new Set(lessons.map((lesson) => lesson.id)).size, 9);
  assert.equal(lessons.reduce((total, lesson) => total + lesson.steps.length, 0), 45);
  for (const level of curriculum.levels) {
    for (const lesson of level.lessons) {
      assert.equal(lesson.level_id, level.id);
      assert.ok(lesson.steps.every((step) => step.target && step.explanation && step.limitation));
    }
  }
});

test("unknown lesson or step IDs safely fall back to valid training content", () => {
  const first = curriculum.levels[0].lessons[0];
  assert.equal(selectTrainingStep(curriculum, "missing", "missing").lesson.id, first.id);
  assert.equal(selectTrainingStep(curriculum, first.id, "missing").step.id, first.steps[0].id);
});

test("deep links select the exact advanced lesson and step without account state", () => {
  const advanced = curriculum.levels[2].lessons[1];
  const step = advanced.steps[4];
  const link = new URL(trainingLink(advanced.id, step.id), "http://example.test");
  const selection = selectTrainingStep(curriculum, link.searchParams.get("lesson"), link.searchParams.get("step"));
  assert.equal(selection.level.ordinal, 3);
  assert.equal(selection.stepIndex, 4);
  assert.equal(selection.step.id, step.id);
});

test("training practice references only published preview lessons and uniquely identified sample events", () => {
  const lessonIds = new Set(curriculum.levels.flatMap((level) => level.lessons.map((lesson) => lesson.id)));
  const eventIds = new Set();
  assert.equal(practice.purpose, "training");
  assert.deepEqual(practice.cases.map((item) => item.level), [1, 2, 3]);
  for (const item of practice.cases) {
    assert.ok(item.id.startsWith("TR-PREVIEW-"));
    assert.ok(item.lesson_ids.every((id) => lessonIds.has(id)));
    assert.ok(item.events.length > 0);
    for (const event of item.events) {
      assert.ok(!eventIds.has(event.id));
      eventIds.add(event.id);
      assert.ok(event.request === null || event.request.path.startsWith("/training/"));
    }
  }
});

test("public content has no exam keys, account credentials, scores, or unlock state", () => {
  const forbidden = new Set(["ground_truth", "answer_key", "expected_evidence_keys", "expected_severity", "expected_disposition", "criterion_guidance", "score", "passed", "unlocked", "password", "api_key"]);
  function inspect(value) {
    if (Array.isArray(value)) value.forEach(inspect);
    else if (value && typeof value === "object") {
      for (const [key, nested] of Object.entries(value)) {
        assert.ok(!forbidden.has(key), `Public content contains forbidden key ${key}`);
        inspect(nested);
      }
    }
  }
  inspect(curriculum);
  inspect(practice);
});
