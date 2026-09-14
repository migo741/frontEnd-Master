import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { cases } from '../labs/01-semantics/cases.js';
import { mode } from './helpers.mjs';
const predictions = JSON.parse(
  await readFile(new URL(`../labs/01-semantics/${mode}/predictions.json`, import.meta.url), 'utf8')
);
for (const item of cases)
  test(`01 / ${item.id}`, async () => {
    assert.notEqual(predictions[item.id], null, '请先填写预测，不要先运行 cases 获得答案');
    assert.deepEqual(predictions[item.id], await item.run());
  });
