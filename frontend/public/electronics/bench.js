const button = document.querySelector('#power');
button.addEventListener('click', () => {
  const on = button.getAttribute('aria-pressed') !== 'true';
  button.setAttribute('aria-pressed', String(on));
  button.textContent = on ? 'Turn power off' : 'Turn power on';
  document.querySelector('#led-glow').classList.toggle('on', on);
  document.querySelector('#status').textContent = on ? 'Power on · approximately 13.6 mA' : 'Power off · 0 mA';
});
const base = 'https://github.com/fritzing/fritzing-parts/blob/27535f2fd02097be9bed229b75aa8e9be282a4a0/';
for (const [label, path] of [
  ['Breadboard graphic', 'svg/core/breadboard/breadboard.svg'],
  ['Arduino UNO Rev3 breadboard graphic', 'svg/core/breadboard/arduino_Uno_Rev3_breadboard.svg'],
  ['220 Ω resistor graphic', 'svg/core/breadboard/resistor_220.svg'],
  ['330 Ω resistor graphic', 'svg/obsolete/breadboard/resistor_330.svg'],
  ['Red LED graphic', 'svg/core/breadboard/LED-5mm-red-leg.svg'],
  ['LED metadata and anode/cathode connector definitions', 'core/LED-generic-5mm_6852162_005.fzp'],
  ['Upstream license', 'LICENSE.txt'],
]) {
  const item = document.createElement('li');
  const link = document.createElement('a');
  link.href = base + path;
  link.textContent = label;
  item.append(link);
  document.querySelector('#sources').append(item);
}
