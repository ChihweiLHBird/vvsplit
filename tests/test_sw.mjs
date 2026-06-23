import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';


const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SOURCE = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');


function loadWorker({ cache, cacheKeys = [], fetchImpl } = {}) {
  const listeners = {};
  const deleted = [];
  const warnings = [];
  let claimed = false;
  let skipped = false;
  const activeCache = cache ?? {
    addAll: async () => {},
    match: async () => undefined,
    put: async () => {},
  };
  const sandbox = {
    URL,
    console: { warn: (...args) => { warnings.push(args); } },
    fetch: fetchImpl ?? (async () => ({ ok: true, clone() { return this; } })),
    caches: {
      open: async () => activeCache,
      keys: async () => cacheKeys,
      delete: async (key) => {
        deleted.push(key);
        return true;
      },
    },
    self: {
      location: { origin: 'https://app.example' },
      clients: {
        claim: async () => { claimed = true; },
      },
      skipWaiting: async () => { skipped = true; },
      addEventListener: (name, handler) => { listeners[name] = handler; },
    },
  };
  vm.runInNewContext(SOURCE, sandbox, { filename: 'sw.js' });
  return {
    listeners,
    deleted,
    warnings,
    wasClaimed: () => claimed,
    wasSkipped: () => skipped,
  };
}


function lifetimeEvent() {
  let lifetime;
  return {
    event: { waitUntil: (promise) => { lifetime = promise; } },
    lifetime: () => lifetime,
  };
}


test('install rejects atomically and keeps the previous worker active', async () => {
  const cache = {
    addAll: async () => { throw new Error('missing shell asset'); },
    put: async () => {},
  };
  const worker = loadWorker({ cache });
  const install = lifetimeEvent();

  worker.listeners.install(install.event);

  await assert.rejects(install.lifetime(), /missing shell asset/);
  assert.equal(worker.wasSkipped(), false);
  assert.deepEqual(worker.deleted, ['bunnysplit-v6']);
});


test('install activates only after the required shell succeeds', async () => {
  let shellInstalled = false;
  const cache = {
    addAll: async () => { shellInstalled = true; },
    put: async () => { assert.equal(shellInstalled, true); },
  };
  const worker = loadWorker({ cache });
  const install = lifetimeEvent();

  worker.listeners.install(install.event);
  await install.lifetime();

  assert.equal(worker.wasSkipped(), true);
});


test('activate deletes only stale bunnysplit caches', async () => {
  const worker = loadWorker({
    cacheKeys: ['bunnysplit-old', 'bunnysplit-v6', 'another-app-cache'],
  });
  const activate = lifetimeEvent();

  worker.listeners.activate(activate.event);
  await activate.lifetime();

  assert.deepEqual(worker.deleted, ['bunnysplit-old']);
  assert.equal(worker.wasClaimed(), true);
});


test('same-origin response returns while cache persistence stays alive', async () => {
  let finishPut;
  const putPending = new Promise((resolve) => { finishPut = resolve; });
  const response = { ok: true, clone() { return { cached: true }; } };
  const cache = {
    match: async () => undefined,
    put: async () => putPending,
  };
  const worker = loadWorker({ cache, fetchImpl: async () => response });
  let responsePromise;
  let lifetimePromise;
  const event = {
    request: {
      method: 'GET',
      mode: 'cors',
      url: 'https://app.example/main.py',
    },
    respondWith: (promise) => { responsePromise = promise; },
    waitUntil: (promise) => { lifetimePromise = promise; },
  };

  worker.listeners.fetch(event);
  const returnedPromptly = await Promise.race([
    responsePromise.then(() => true),
    new Promise((resolve) => setImmediate(() => resolve(false))),
  ]);
  assert.equal(returnedPromptly, true);
  assert.ok(lifetimePromise);

  let lifetimeSettled = false;
  lifetimePromise.then(() => { lifetimeSettled = true; });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(lifetimeSettled, false);

  finishPut();
  assert.equal(await responsePromise, response);
  await lifetimePromise;
});


test('cross-origin response returns while cache persistence stays alive', async () => {
  let finishPut;
  const putPending = new Promise((resolve) => { finishPut = resolve; });
  const response = { ok: true, type: 'cors', clone() { return this; } };
  const cache = {
    match: async () => undefined,
    put: async () => putPending,
  };
  const worker = loadWorker({ cache, fetchImpl: async () => response });
  let responsePromise;
  let lifetimePromise;
  const event = {
    request: {
      method: 'GET',
      mode: 'cors',
      url: 'https://pyscript.net/releases/2024.11.1/core.js',
    },
    respondWith: (promise) => { responsePromise = promise; },
    waitUntil: (promise) => { lifetimePromise = promise; },
  };

  worker.listeners.fetch(event);
  const returnedPromptly = await Promise.race([
    responsePromise.then(() => true),
    new Promise((resolve) => setImmediate(() => resolve(false))),
  ]);
  assert.equal(returnedPromptly, true);
  assert.ok(lifetimePromise);

  let lifetimeSettled = false;
  lifetimePromise.then(() => { lifetimeSettled = true; });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(lifetimeSettled, false);

  finishPut();
  assert.equal(await responsePromise, response);
  await lifetimePromise;
});


test('a cache quota failure does not discard a successful network response', async () => {
  const response = { ok: true, clone() { return this; } };
  const cache = {
    match: async () => undefined,
    put: async () => { throw new Error('quota exceeded'); },
  };
  const worker = loadWorker({ cache, fetchImpl: async () => response });
  let responsePromise;
  let lifetimePromise;
  const event = {
    request: {
      method: 'GET',
      mode: 'cors',
      url: 'https://app.example/main.py',
    },
    respondWith: (promise) => { responsePromise = promise; },
    waitUntil: (promise) => { lifetimePromise = promise; },
  };

  worker.listeners.fetch(event);

  assert.equal(await responsePromise, response);
  await lifetimePromise;
  assert.equal(worker.warnings.length, 1);
});
