const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('holograms-local/hologram-display.js', 'utf8').replace('  const styles=`', '  globalThis.geometry = definitions;\n  const styles=`');
const context = { HTMLElement: class {}, customElements: { get: () => true } };
vm.createContext(context);
vm.runInContext(code, context);
for (const id of ['uno','breadboard','led','resistor','jumper']) {
 const parts = context.geometry[id].parts();
 for (const part of parts) {
  if (!part.points.length || !part.points.every(p => p.length === 3 && p.every(Number.isFinite))) throw Error(id + ': invalid vertices');
  for (const indices of [...part.lines, ...part.faces]) if (!indices.every(i => Number.isInteger(i) && i >= 0 && i < part.points.length)) throw Error(id + ': invalid mesh index');
 }
 console.log(id + ': ' + parts.length + ' valid parts, ' + parts.reduce((n,p) => n + p.points.length, 0) + ' vertices');
}
