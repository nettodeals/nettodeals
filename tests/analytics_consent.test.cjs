// Run with: node --test tests/analytics_consent.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../nettodeals/static/analytics.js'), 'utf8');
const KEY = 'nettodeals.analytics.v1';
function setup(saved = null, path = '/', brokenStorage = false) {
  const elements = new Map();
  const ids = ['analytics-consent', 'analytics-settings', 'analytics-close', 'analytics-title', 'analytics-accept', 'analytics-reject'];
  ids.forEach(id => elements.set(id, {hidden: true, handlers: {}, addEventListener(event, cb) {this.handlers[event] = cb;}, setAttribute() {}, focus() {}}));
  const scripts = [], cookies = [], events = {};
  let reloads = 0, stored = saved, tick;
  const document = {getElementById: id => elements.get(id), referrer: 'https://example.org/?secret=123', createElement: () => ({}), head: {appendChild: el => scripts.push(el)}};
  Object.defineProperty(document, 'cookie', {get: () => '_ga=abc; _ga_GQGD9NXG70=xyz; admin_session=keep', set: value => cookies.push(value)});
  const window = {location: {pathname: path, hostname: 'www.nettodeals.ch', origin: 'https://www.nettodeals.ch', reload: () => reloads++}, addEventListener: (name, cb) => {events[name] = cb;}};
  const context = {window, document, localStorage: {getItem() {if (brokenStorage) throw Error('blocked'); return stored;}, setItem(key, val) {if (brokenStorage) throw Error('blocked'); stored = val;}}, setInterval: fn => {tick = fn; return 1;}, clearInterval() {}, Date};
  vm.runInNewContext(source, context);
  return {window, elements, scripts, cookies, click: id => elements.get('analytics-' + id).handlers.click(), stored: () => stored, reloads: () => reloads, storage: value => {stored = value; events.storage({key: KEY});}, tick: () => tick()};
}
const record = choice => JSON.stringify({choice, expires: Date.now() + 86400000});
test('no Google script before consent; decline persists without loading', () => {
  const s = setup(); assert.equal(s.scripts.length, 0); assert.equal(s.elements.get('analytics-consent').hidden, false);
  s.click('reject'); assert.equal(s.scripts.length, 0); assert.equal(JSON.parse(s.stored()).choice, 'denied');
});
test('accept loads once with ad consent denied and cleaned URLs', () => {
  const s = setup(); s.click('accept'); s.click('accept'); assert.equal(s.scripts.length, 1);
  const commands = s.window.dataLayer.map(args => Array.from(args));
  assert.equal(commands[0][2].ad_storage, 'denied');
  assert.equal(commands[2][2].page_location, 'https://www.nettodeals.ch/');
  assert.equal(commands[2][2].page_referrer, 'https://example.org/');
});
test('return visits respect saved grant or denial', () => {
  assert.equal(setup(record('granted')).scripts.length, 1);
  assert.equal(setup(record('denied')).scripts.length, 0);
});
test('withdraw disables measurement and clears only integration cookies', () => {
  const s = setup(record('granted')); s.click('settings'); s.click('reject');
  assert.equal(s.window['ga-disable-G-GQGD9NXG70'], true); assert.equal(s.reloads(), 1);
  assert.ok(s.cookies.some(c => c.includes('Domain=nettodeals.ch')));
  assert.ok(s.cookies.every(c => !c.includes('admin_session')));
});
test('cross-tab withdrawal stops loaded tag', () => {
  const s = setup(record('granted')); s.storage(record('denied'));
  assert.equal(s.window['ga-disable-G-GQGD9NXG70'], true); assert.equal(s.reloads(), 1);
});
test('expired, malformed and unavailable storage default to no tag', () => {
  for (const value of ['broken', JSON.stringify({choice:'granted', expires:1}), JSON.stringify({choice:'granted', expires:'forever'})]) assert.equal(setup(value).scripts.length, 0);
  const s = setup(null, '/', true); assert.equal(s.scripts.length, 0); s.click('accept'); assert.equal(s.scripts.length, 1);
});
test('admin paths never initialise analytics even with prior consent', () => {
  const s = setup(record('granted'), '/admin/deals/1'); assert.equal(s.scripts.length, 0); assert.equal(s.window.dataLayer, undefined);
});
