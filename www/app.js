/* Vasukii AR - test build UI.  No bundler: plain JS. */

// Where Scene Viewer (Google AR) downloads the .glb files from. It needs a public https URL.
// Served straight from this GitHub repo through jsDelivr. Change if you host models elsewhere.
const MODEL_BASE_HTTPS = 'https://cdn.jsdelivr.net/gh/Tushar9850/Vasukii-AR@main/www/models/';

const $ = (id) => document.getElementById(id);
const viewer = $('viewer');
const state = { plant: 'snake', pot: 'terracotta', size: 'M' };
let catalog = null;

const isNative = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());

function fileName() { return `${state.plant}_${state.pot}_${state.size}.glb`; }
function plant() { return catalog.plants.find((p) => p.id === state.plant); }

function toast(msg, ms = 4200) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), ms);
}

function render() {
  const p = plant();
  $('plantName').textContent = p.name;
  $('plantLatin').textContent = p.latin;
  $('plantBlurb').textContent = p.blurb;
  $('careLight').textContent = '\u2600 ' + p.light;
  $('careWater').textContent = '\uD83D\uDCA7 ' + p.water;
  $('dims').textContent = `${p.heightsCm[state.size]} cm tall \u00B7 ${p.widthsCm[state.size]} cm wide`;

  $('plantChips').innerHTML = catalog.plants.map((x) =>
    `<button class="chip ${x.id === state.plant ? 'on' : ''}" data-plant="${x.id}">${x.name}</button>`).join('');
  $('potSwatches').innerHTML = catalog.pots.map((x) =>
    `<button class="sw ${x.id === state.pot ? 'on' : ''}" data-pot="${x.id}"><i style="background:${x.hex}"></i>${x.label}</button>`).join('');
  $('sizeSeg').innerHTML = catalog.sizes.map((x) =>
    `<button class="${x.id === state.size ? 'on' : ''}" data-size="${x.id}">${x.label}<small>${p.heightsCm[x.id]} cm</small></button>`).join('');

  $('loading').classList.remove('hide');
  viewer.setAttribute('src', 'models/' + fileName());
  viewer.setAttribute('ios-src', 'models/' + fileName());
}

document.addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.plant) { state.plant = b.dataset.plant; render(); }
  else if (b.dataset.pot) { state.pot = b.dataset.pot; render(); }
  else if (b.dataset.size) { state.size = b.dataset.size; render(); }
});

viewer.addEventListener('load', () => $('loading').classList.add('hide'));
viewer.addEventListener('error', () => { $('loading').textContent = 'Could not load model'; });

async function openAR() {
  const url = MODEL_BASE_HTTPS + fileName();
  const title = `${plant().name} (${state.pot}, ${state.size})`;
  if (isNative) {
    const SV = window.Capacitor.Plugins && window.Capacitor.Plugins.SceneViewer;
    if (!SV) { toast('AR launcher missing in this build.'); return; }
    try {
      const r = await SV.open({ file: url, title });
      if (r && r.launched === false) {
        toast('AR needs "Google Play Services for AR" and the Google app. Install/update them from Play Store, then try again.', 7000);
      }
    } catch (err) {
      toast('Could not open AR: ' + (err && err.message ? err.message : err), 7000);
    }
  } else if (viewer.canActivateAR) {
    viewer.activateAR();
  } else {
    toast('AR works on a phone. Install the APK (or open this page on an AR-capable phone).');
  }
}
$('arBtn').addEventListener('click', openAR);

fetch('plants.json').then((r) => r.json()).then((c) => {
  catalog = c;
  render();
  if (!isNative) $('hint').textContent = 'Running in a browser. AR works on phones.';
}).catch((e) => toast('Failed to load catalog: ' + e.message, 8000));
