/* ScavScrap local holograms. Dependency-free SVG with perspective-projected 3D geometry.
 * Usage: <hologram-display device="smartwatch|headphones|laptop|phone|speaker">
 * No network calls, textures, brands, or recognition output. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const TAU = Math.PI * 2;
  const make = (tag, attrs = {}, text) => {
    const el = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    if (text != null) el.textContent = text;
    return el;
  };
  const add = (a, b) => a.map((v, i) => v + b[i]);
  const rotate = ([x,y,z], [rx=0,ry=0,rz=0]) => {
    [y,z]=[y*Math.cos(rx)-z*Math.sin(rx),y*Math.sin(rx)+z*Math.cos(rx)];
    [x,z]=[x*Math.cos(ry)+z*Math.sin(ry),-x*Math.sin(ry)+z*Math.cos(ry)];
    return [x*Math.cos(rz)-y*Math.sin(rz),x*Math.sin(rz)+y*Math.cos(rz),z];
  };
  const mesh = () => ({ points:[], lines:[], faces:[] });
  function line(m, points, close=false) {
    const start=m.points.length; m.points.push(...points);
    const ids=points.map((_,i)=>start+i);
    if(close) ids.push(start);
    m.lines.push(ids); return ids;
  }
  function box(m, w,h,d, center=[0,0,0], rotation=[0,0,0]) {
    const s=m.points.length;
    [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].forEach(p=>m.points.push(add(rotate([p[0]*w/2,p[1]*h/2,p[2]*d/2],rotation),center)));
    [[0,1,2,3,0],[4,5,6,7,4],[0,4],[1,5],[2,6],[3,7]].forEach(ids=>m.lines.push(ids.map(i=>i+s)));
    [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]].forEach(ids=>m.faces.push(ids.map(i=>i+s)));
  }
  function ring(m,r,center=[0,0,0],axis='z',n=28) {
    const pts=Array.from({length:n},(_,i)=>{const a=TAU*i/n;return add(axis==='x'?[0,r*Math.cos(a),r*Math.sin(a)]:axis==='y'?[r*Math.cos(a),0,r*Math.sin(a)]:[r*Math.cos(a),r*Math.sin(a),0],center)});
    return line(m,pts,true);
  }
  function cylinder(m,r,len,axis='x',center=[0,0,0],n=24) {
    const dim={x:0,y:1,z:2}[axis],a=[...center],b=[...center];a[dim]-=len/2;b[dim]+=len/2;
    const first=ring(m,r,a,axis,n),last=ring(m,r,b,axis,n);
    for(let i=0;i<n;i+=3)m.lines.push([first[i],last[i]]);
    m.faces.push(first.slice(0,-1),last.slice(0,-1));
  }
  function gear(m,r,center=[0,0,0],axis='z') {
    const pts=Array.from({length:48},(_,i)=>{const a=TAU*i/48,rr=r*(i%4<2?1:.83);return add(axis==='x'?[0,rr*Math.cos(a),rr*Math.sin(a)]:[rr*Math.cos(a),rr*Math.sin(a),0],center)});
    line(m,pts,true);ring(m,r*.32,center,axis,12);
  }
  function dial(m,r,center=[0,0,0]) {
    ring(m,r,center);ring(m,r*.83,center);
    for(let i=0;i<12;i++){const a=TAU*i/12;line(m,[add([Math.cos(a)*r*.7,Math.sin(a)*r*.7,0],center),add([Math.cos(a)*r*.82,Math.sin(a)*r*.82,0],center)])}
    line(m,[add([-r*.4,r*.25,0],center),center,add([r*.13,-r*.57,0],center)]);
  }
  function rivets(m,w,h,z){for(const x of [-1,1])for(const y of [-1,1])ring(m,1.3,[x*(w/2-4),y*(h/2-4),z],'z',6)}
  // Optional phone engraving: fixed irregularities keep the ink strokes stable in motion.
  function hatch(m,points) {
    const start=m.points.length;m.points.push(...points);
    (m.hatching ||= []).push(points.map((_,i)=>start+i));
  }
  function engravedPhoneParts() {
    const parts=definitions.phone.parts();
    parts.forEach((p,index)=>{
      const [w,h,d]=[[58,112,2],[54,106,2],[50,102,3],[43,76,8],[58,112,5]][index];
      // Short edge hatching leaves the pressure dial and circuitry legible.
      for(let y=-h/2+6;y<h/2-5;y+=3.5)for(const sign of [-1,1]) {
        hatch(p,[[sign*(w/2-1),y,d/2+.2],[sign*(w/2-4),y+1.7,d/2+.3]]);
        hatch(p,[[sign*w/2,y,-d/2],[sign*(w/2+.15),y+.6,d/2]]);
      }
      if(index===3||index===4)for(let y=-h/2+8;y<h/2-7;y+=4) {
        hatch(p,[[-w/2+7,y,-d/2-.2],[0,y+1,-d/2-.3],[w/2-7,y+1.6,-d/2-.2]]);
      }
      if(index===0)for(const y of [-h/2+8,h/2-8]) {
        line(p,[[-w/2+6,y,1.2],[-w/2+6,y+(y<0?7:-7),1.2]]);
        line(p,[[w/2-6,y,1.2],[w/2-6,y+(y<0?7:-7),1.2]]);
      }
      if(index===1)for(let i=0;i<32;i++){
        const a=TAU*i/32;hatch(p,[[21*Math.cos(a),-18+21*Math.sin(a),2.2],[23*Math.cos(a),-18+23*Math.sin(a),2.2]]);
      }
    });
    return parts;
  }
  const part=(label,position,axis,amount,build)=>{const m=mesh();build(m);return {label,position,axis,amount,...m}};
  const definitions={
    smartwatch:{name:'Smartwatch',no:'01',subtitle:'CASE / DIAL / ARTICULATED STRAP',parts:()=>[
      part('Upper strap',[0,-70,0],[0,-1,0],22,m=>{box(m,27,28,5);line(m,[[-10,-8,3],[10,-8,3]]);line(m,[[-10,8,3],[10,8,3]])}),
      part('Upper link',[0,-39,0],[0,-1,0],12,m=>{box(m,29,18,5);rivets(m,29,18,3)}),
      part('Pressure dial',[0,-8,11],[0,-1,0],7,m=>{box(m,41,42,2);dial(m,15,[0,0,2]);rivets(m,41,42,2)}),
      part('Case + crown',[0,8,0],[0,1,0],5,m=>{box(m,48,48,13);cylinder(m,5,8,'x',[28,-5,0]);gear(m,10,[-8,3,7]);gear(m,7,[8,2,7]);rivets(m,48,48,7)}),
      part('Lower link',[0,47,0],[0,1,0],13,m=>{box(m,29,19,5);rivets(m,29,19,3)}),
      part('Buckle strap',[0,78,0],[0,1,0],23,m=>{box(m,27,28,5);for(let y=-8;y<=8;y+=8)ring(m,2,[0,y,3],'z',8)})]},
    headphones:{name:'Over-ear headphones',no:'02',subtitle:'HEADBAND / CUSHIONS / ACOUSTICS',parts:()=>[
      part('Copper headband',[0,-13,0],[0,-1,0],13,m=>{for(const z of [-9,9])for(const r of [55,61])line(m,Array.from({length:25},(_,i)=>[Math.cos(Math.PI+i*Math.PI/24)*r,Math.sin(Math.PI+i*Math.PI/24)*r,z]));box(m,8,30,20,[-58,10,0]);box(m,8,30,20,[58,10,0])}),
      ...[-1,1].flatMap(s=>[
        part(s<0?'Left ear cup':'Right ear cup',[s*69,23,0],[s,0,0],10,m=>{cylinder(m,30,15);ring(m,21,[s*8,0,0],'x');gear(m,13,[s*8,0,0],'x')}),
        part(s<0?'Left driver':'Right driver',[s*95,23,0],[s,0,0],20,m=>{cylinder(m,24,4);ring(m,16,[0,0,0],'x');ring(m,7,[s*3,0,0],'x')}),
        part(s<0?'Left cushion':'Right cushion',[s*117,23,0],[s,0,0],28,m=>{cylinder(m,29,10);cylinder(m,19,10)})
      ])]},
    laptop:{name:'Laptop',no:'03',subtitle:'HINGED LID / KEYBOARD / CHASSIS',parts:()=>[
      part('Opened lid',[0,-51,-36],[0,-1,0],20,m=>{box(m,132,82,4,[0,0,0],[-.35,0,0]);rivets(m,132,82,3)}),
      part('Screen panel',[0,-46,-23],[0,-1,0],13,m=>{box(m,120,70,2,[0,0,0],[-.35,0,0]);gear(m,17,[-23,-1,3]);gear(m,11,[3,4,3]);dial(m,15,[33,0,3])}),
      part('Keyboard deck',[0,15,0],[0,1,0],4,m=>{box(m,136,5,88);for(let row=0;row<4;row++)for(let col=0;col<10;col++)box(m,9,1,7,[-54+col*12,-3,-27+row*10]);box(m,40,1,18,[0,-3,28]);line(m,[[-60,-4,35],[-60,-4,-35],[60,-4,-35]])}),
      part('Circuit layer',[0,37,0],[0,1,0],12,m=>{box(m,112,2,68);for(const x of [-35,0,35])box(m,20,3,23,[x,-3,0]);gear(m,12,[-32,0,0],'x');line(m,[[-48,-2,22],[0,-2,22],[0,-2,-22],[48,-2,-22]])}),
      part('Base plate',[0,61,0],[0,1,0],23,m=>{box(m,136,4,88);for(const x of [-55,55])for(const z of [-30,30])cylinder(m,4,3,'y',[x,4,z],12)})]},
    phone:{name:'Smartphone',no:'04',subtitle:'GLASS / CIRCUITRY / POWER CELL',parts:()=>[
      part('Front glass',[0,0,43],[0,0,1],25,m=>{box(m,58,112,2);rivets(m,58,112,2)}),
      part('Dial display',[0,0,22],[0,0,1],12,m=>{box(m,54,106,2);dial(m,20,[0,-18,2]);gear(m,11,[-10,24,2]);gear(m,8,[9,28,2]);line(m,[[-17,43,2],[17,43,2]])}),
      part('Mainboard',[0,0,0],[0,0,1],0,m=>{box(m,50,102,3);for(const y of [-33,0,33]){box(m,18,16,3,[-8,y,3]);line(m,[[4,y-6,3],[17,y-6,3],[17,y+12,3]])}rivets(m,50,102,3)}),
      part('Battery',[0,7,-23],[0,0,-1],13,m=>{box(m,43,76,8);line(m,[[-15,-29,5],[15,-29,5]]);line(m,[[0,-12,5],[0,2,5]]);line(m,[[-7,-5,5],[7,-5,5]]);line(m,[[-7,22,5],[7,22,5]])}),
      part('Back plate',[0,0,-46],[0,0,-1],25,m=>{box(m,58,112,5);for(const y of [-37,-20])cylinder(m,6,3,'z',[-17,y,-4],16);rivets(m,58,112,-3)})]},
    speaker:{name:'Portable speaker',no:'05',subtitle:'GRILLE / DRIVER / PASSIVE RADIATORS',parts:()=>[
      part('Left end cap',[-112,0,0],[-1,0,0],24,m=>{cylinder(m,34,10);ring(m,28,[-6,0,0],'x');gear(m,12,[-6,0,0],'x')}),
      part('Left radiator',[-87,0,0],[-1,0,0],17,m=>{cylinder(m,27,5);ring(m,19,[-3,0,0],'x');ring(m,8,[-4,0,0],'x')}),
      part('Woven grille',[-22,0,0],[-1,0,0],5,m=>{cylinder(m,34,79);for(let x=-32;x<=32;x+=8)ring(m,34,[x,0,0],'x');for(let i=0;i<12;i++){const a=TAU*i/12;line(m,[[-39,34*Math.cos(a),34*Math.sin(a)],[39,34*Math.cos(a+.2),34*Math.sin(a+.2)]])}box(m,35,4,12,[0,-35,0])}),
      part('Acoustic driver',[43,0,0],[1,0,0],12,m=>{cylinder(m,28,15);for(const r of [8,16,23])ring(m,r,[9,0,0],'x');cylinder(m,12,12,'x',[-12,0,0])}),
      part('Right radiator',[78,0,0],[1,0,0],20,m=>{cylinder(m,27,5);ring(m,18,[4,0,0],'x')}),
      part('Right end cap',[105,0,0],[1,0,0],29,m=>{cylinder(m,34,10);ring(m,28,[6,0,0],'x');for(let i=0;i<6;i++){const a=TAU*i/6;cylinder(m,2,2,'x',[6,29*Math.cos(a),29*Math.sin(a)],8)}})
    ]}
  };
  // Original illustrative geometry from DESIGN.md, First demo inventory (lines 43–48).
  // Proportions aid identification; these are not measured manufacturing models.
  Object.assign(definitions, {
    uno: {name:'Arduino UNO R3',no:'E1',subtitle:'PCB / USB-B / HEADERS',parts:()=>[
      part('UNO board',[0,0,0],[0,0,-1],12,m=>{box(m,138,104,4);for(const x of [-60,60])for(const y of [-43,43])ring(m,3,[x,y,3],'z',12);line(m,[[-55,-27,3],[5,-27,3],[5,21,3],[50,21,3]]);line(m,[[-48,-22,3],[-12,-22,3],[-12,32,3],[42,32,3]])}),
      part('USB-B connector',[-51,-30,12],[-1,0,1],16,m=>{box(m,28,26,22);box(m,22,18,2,[0,0,12]);box(m,10,7,4,[0,0,14])}),
      part('Power jack',[-52,28,11],[-1,0,1],12,m=>{box(m,25,20,18);cylinder(m,6,25,'x');ring(m,3,[-13,0,0],'x',12)}),
      part('ATmega package',[14,8,9],[0,0,1],18,m=>{box(m,55,17,10);for(let i=0;i<14;i++)for(const s of [-1,1])box(m,1.5,8,2,[-25+i*3.8,s*12,-3]);ring(m,2,[-22,0,6],'z',10)}),
      part('Socket headers',[9,0,9],[0,0,1],12,m=>{for(const y of [-44,44]){box(m,95,9,13,[0,y,0]);for(let i=0;i<16;i++)box(m,3,3,1,[-43+i*5.7,y,7]);}box(m,15,10,5,[-3,-23,0]);cylinder(m,5,12,'z',[-26,29,0],12)})
    ]},
    breadboard: {name:'Solderless breadboard',no:'E2',subtitle:'TERMINAL GROUPS / CENTER CHANNEL',parts:()=>[
      part('Insulating body',[0,0,0],[0,0,-1],8,m=>{box(m,190,94,12);box(m,182,7,2,[0,0,7]);for(const y of [-40,40])line(m,[[-87,y,7],[87,y,7]])}),
      part('Terminal holes',[0,0,7],[0,0,1],13,m=>{for(let col=0;col<25;col++)for(const side of [-1,1])for(let row=0;row<5;row++)ring(m,1.4,[-84+col*7,side*(9+row*5),0],'z',6)}),
      part('Power rail holes',[0,0,7],[0,0,1],8,m=>{for(let col=0;col<25;col++)for(const y of [-44,-36,36,44])ring(m,1.2,[-84+col*7,y,0],'z',6)})
    ]},
    led: {name:'Red LED',no:'E3',subtitle:'ANODE (+) / CATHODE (-)',parts:()=>[
      part('Lens and dome',[0,-22,0],[0,-1,0],16,m=>{cylinder(m,22,34,'y');for(let i=0;i<7;i++){const a=i*Math.PI/14;ring(m,22*Math.cos(a),[0,-17-22*Math.sin(a),0],'y',28)}for(let i=0;i<12;i++){const a=i*TAU/12;line(m,Array.from({length:9},(_,j)=>{const b=j*Math.PI/16;return [22*Math.cos(a)*Math.cos(b),-17-22*Math.sin(b),22*Math.sin(a)*Math.cos(b)]}))}cylinder(m,25,5,'y',[0,19,0]);}),
      part('Anode — long lead',[10,39,0],[1,0,0],12,m=>{box(m,3,88,3);line(m,[[0,-44,0],[0,-53,0],[-9,-59,0]])}),
      part('Cathode — short lead',[-10,33,0],[-1,0,0],12,m=>{box(m,3,76,3);box(m,12,10,6,[0,-42,0]);line(m,[[-8,-49,0],[8,-49,0]])})
    ]},
    resistor: {name:'330 O resistor',no:'E4',subtitle:'ORANGE / ORANGE / BROWN / GOLD',parts:()=>[
      part('Resistive body',[0,0,0],[0,0,1],9,m=>{cylinder(m,17,68,'x',[0,0,0],28);cylinder(m,13,12,'x',[-38,0,0]);cylinder(m,13,12,'x',[38,0,0]);}),
      part('330 O band positions',[0,0,0],[0,-1,0],10,m=>{for(const x of [-22,-9,4,24]){ring(m,17.5,[x,0,0],'x',32);ring(m,17.5,[x+4,0,0],'x',32)}}),
      part('Left lead',[-66,0,0],[-1,0,0],17,m=>{cylinder(m,1.7,46,'x',[0,0,0],8)}),
      part('Right lead',[66,0,0],[1,0,0],17,m=>{cylinder(m,1.7,46,'x',[0,0,0],8)})
    ]},
    jumper: {name:'Male-to-male jumpers ×2',no:'E5',subtitle:'INSULATION / MALE PINS',parts:()=>[-1,1].flatMap((side,index)=>[
      part(index?'Ground jumper':'Supply jumper',[0,side*24,0],[0,side,0],16,m=>{for(const dz of [-2,0,2])line(m,Array.from({length:45},(_,i)=>{const t=i/44;return [-67+134*t,16*Math.sin(t*Math.PI*2),dz+15*Math.sin(t*Math.PI)]}))}),
      part(index?'Ground male ends':'Supply male ends',[0,side*24,0],[0,side,0],20,m=>{for(const s of [-1,1]){box(m,20,9,9,[s*77,0,0]);box(m,17,2,2,[s*95,0,0]);line(m,[[s*69,-3,5],[s*85,-3,5]])}})
    ])}
  });

  const styles=`
    :host{display:block;min-width:0;color:#f5d27a;font-family:Georgia,serif;contain:content}
    *{box-sizing:border-box}.instrument{position:relative;padding:24px 12px 26px;background:radial-gradient(ellipse at 50% 43%,#382818 0,#241a11 30%,#1a140e 65%)}
    .topline{display:flex;justify-content:space-between;padding:0 15px;font:9px 'Courier New',monospace;letter-spacing:1.6px;color:#b08b4d}.topline span:last-child{color:#8c714a}
    button{display:block;width:100%;padding:0;border:0;background:transparent;color:inherit;cursor:pointer;touch-action:manipulation;border-radius:50%;outline-offset:-16px}button:focus-visible{outline:1px dashed #e8b04a}
    svg{display:block;width:100%;height:auto;overflow:visible}.beam{animation:beam 6s ease-in-out infinite}.scene{filter:drop-shadow(0 0 2px #e8b04a88);animation:flicker 7.7s linear infinite}.wire{fill:none;stroke:#e8b04a;stroke-width:.85;stroke-linejoin:round;stroke-linecap:round}.skin{fill:#e8b04a;fill-opacity:.025;stroke:none}.vertices{fill:none;stroke:#f5d27a;stroke-width:1.9;stroke-linecap:round;opacity:.8}.labels{opacity:0;transition:opacity .5s}.expanded .labels{opacity:1}.leader{fill:none;stroke:#bd8b3c;stroke-width:.65;opacity:.8}.label{fill:#f5d27a;font:9px 'Courier New',monospace;paint-order:stroke;stroke:#1a140e;stroke-width:3px;stroke-linejoin:round}
    h2{font-weight:400;font-size:24px;margin:0 0 9px;text-align:center;letter-spacing:.3px}.subtitle{text-align:center;font:8px 'Courier New',monospace;letter-spacing:1.5px;color:#b08b4d}.hint{text-align:center;font:9px 'Courier New',monospace;color:#8c714a;letter-spacing:1px;margin-top:16px}
    .engraved{background:radial-gradient(ellipse at 48% 42%,#f1dfb8,#d6ba82 75%,#baa06c);color:#382515}
    .engraved .topline,.engraved .subtitle,.engraved .hint{color:#624520}.engraved h2{color:#382515}
    .engraved .scene{filter:none;animation:none}.engraved .wire{stroke:#422b16;stroke-width:1.1}
    .engraved .skin{fill:#d7b67b;fill-opacity:.18}.engraved .vertices{display:none}
    .engraved .hatching{fill:none;stroke:#61401f;stroke-width:.48;stroke-linecap:round;opacity:.66}
    .engraved .ink-echo{fill:none;stroke:#51351b;stroke-width:.45;opacity:.32;stroke-linejoin:round;stroke-linecap:round}
    .engraved .leader{stroke:#65421c}.engraved .label{fill:#382515;stroke:#e7d0a0;font-family:Georgia,serif;font-style:italic;font-size:10px}
    .engraved .beam{opacity:.18;animation:none}.engraved button:focus-visible{outline-color:#624520}
    .backdrop-controls{margin:18px 12px 0;padding:14px 0 0;border-top:1px solid #8c6a3b55;font:11px/1.5 Georgia,serif;color:#51351b}
    .backdrop-controls .control-row{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:9px}
    .backdrop-controls select{max-width:65%;border:1px solid #8c6a3b;border-radius:3px;padding:6px;background:#efdab0;color:#382515;font:12px Georgia,serif}
    .backdrop-controls input{width:55%;accent-color:#795525}.backdrop-controls output{min-width:30px;text-align:right}
    .backdrop-controls :focus-visible{outline:2px solid #624520;outline-offset:3px}.backdrop-controls small{display:block;color:#795525;margin-top:8px}
    :host([compact]){aspect-ratio:1;background:#dcc38e}:host([compact]) .instrument{padding:0;background:radial-gradient(ellipse at center,#ead5a5,#dcc38e 78%)}:host([compact]) button{border-radius:0;aspect-ratio:1}:host([compact]) svg{width:100%;height:100%;aspect-ratio:1}:host([compact]) .beam{display:none}:host([compact]) .topline,:host([compact]) h2,:host([compact]) .subtitle,:host([compact]) .hint,:host([compact]) .backdrop-controls{display:none}
    @keyframes beam{50%{opacity:.55}}@keyframes flicker{0%,95%,97%,100%{opacity:1}95.5%{opacity:.72}96.5%{opacity:.9}98%{opacity:.8}}
    @media(prefers-reduced-motion:reduce){.beam,.scene{animation:none}.labels{transition:none}}
  `;
  let sequence=0;
  class HologramDisplay extends HTMLElement {
    static get observedAttributes(){return ['device','variant']}
    constructor(){super();this.attachShadow({mode:'open'});this.frame=0;this.amount=0;this.time=0;this.visible=true;this.pinned=false;this.hovered=false;this.focused=false;this.motion=matchMedia('(prefers-reduced-motion: reduce)');}
    connectedCallback(){this.mount()}
    disconnectedCallback(){cancelAnimationFrame(this.frame);this.observer?.disconnect()}
    attributeChangedCallback(){if(this.isConnected)this.mount()}
    mount(){
      cancelAnimationFrame(this.frame);this.observer?.disconnect();
      const id=this.getAttribute('device')||'smartwatch';
      const variant=this.getAttribute('variant');
      const def=variant==='drafting'&&definitions[id]
        ? {...definitions[id],engraved:true,subtitle:'PEN & INK / DRAFTING GRID',parts:id==='phone'?engravedPhoneParts:definitions[id].parts}
        : definitions[id]&&(variant==='engraved'||(id==='phone'&&variant==='engraved-backdrop'))
        ? {...definitions[id],engraved:true,subtitle:'PEN & INK / HAND-DRAWN STUDY',parts:id==='phone'?engravedPhoneParts:definitions[id].parts}
        : definitions[id];
      if(!def){this.shadowRoot.textContent='Unknown hologram device.';return}
      this.def=def;this.parts=def.parts();this.uid=`holo-${++sequence}`;
      this.shadowRoot.innerHTML=`<style>${styles}</style><section class="instrument"><div class="topline"><span>SPECIMEN ${def.no}</span><span>AMBER / EXPLODED</span></div><button type="button" aria-label="Expand ${def.name} assembly and reveal part labels" aria-pressed="false"><svg viewBox="0 0 500 500" role="img" aria-label="Exploded wireframe ${def.name}"></svg></button><h2>${def.name}</h2><div class="subtitle">${def.subtitle}</div><div class="hint">HOVER TO INSPECT Â· TAP TO HOLD</div></section>`;
      this.button=this.shadowRoot.querySelector('button');this.svg=this.shadowRoot.querySelector('svg');
      if(this.hasAttribute('compact')){
        this.svg.setAttribute('viewBox','25 5 450 450');
        this.style.borderRadius='50%';
        this.style.overflow='hidden';
      }
      this.shadowRoot.querySelector('.instrument').classList.toggle('engraved',!!def.engraved);
      const defs=make('defs');
      const grad=make('linearGradient',{id:this.uid+'-beam',x1:'0',y1:'1',x2:'0',y2:'0'});grad.append(make('stop',{offset:'0%','stop-color':'#e8b04a','stop-opacity':'.2'}),make('stop',{offset:'100%','stop-color':'#e8b04a','stop-opacity':'0'}));defs.append(grad);
      const brass=make('linearGradient',{id:this.uid+'-brass',x1:'0',y1:'0',x2:'1',y2:'1'});for(const [offset,color] of [['0%','#5a3c1c'],['28%','#c69c56'],['50%','#725128'],['74%','#e0bb70'],['100%','#51381e']])brass.append(make('stop',{offset,'stop-color':color}));defs.append(brass);
      const clip=make('clipPath',{id:this.uid+'-clip'});clip.append(make('circle',{cx:250,cy:230,r:188}));defs.append(clip);this.svg.append(defs);
      const frame=make('g');for(const [r,width,color] of [[205,7,`url(#${this.uid}-brass)`],[196,1,'#a67d3c'],[190,2,'#745326'],[210,.5,'#76552e']])frame.append(make('circle',{cx:250,cy:230,r,fill:'none',stroke:color,'stroke-width':width}));
      for(let i=0;i<100;i++){const a=TAU*i/100,r=i%5?199:195;frame.append(make('path',{d:`M${250+Math.sin(a)*r},${230+Math.cos(a)*r}L${250+Math.sin(a)*202},${230+Math.cos(a)*202}`,stroke:'#dab165','stroke-width':i%5?.45:1}))}
      for(let i=0;i<12;i++){const a=TAU*i/12,x=250+Math.sin(a)*205,y=230+Math.cos(a)*205;frame.append(make('circle',{cx:x,cy:y,r:3.3,fill:'#b78b45',stroke:'#382719','stroke-width':1}),make('path',{d:`M${x-1.5},${y-1}l3,2`,stroke:'#47301b','stroke-width':1}))}
      this.svg.append(frame);
      const clipped=make('g',{'clip-path':`url(#${this.uid}-clip)`});
      if(def.engraved&&['engraved-backdrop','drafting'].includes(variant))this.addBackdropOptions(clipped,defs,variant==='drafting'?'grid':'spotlight');
      clipped.append(make('path',{class:'beam',d:'M210 448 L116 115 Q250 60 384 115 L290 448 Z',fill:`url(#${this.uid}-beam)`}));
      this.scene=make('g',{class:'scene'});clipped.append(this.scene);
      for(const p of this.parts){p.group=make('g');p.fill=make('path',{class:'skin'});p.wire=make('path',{class:'wire'});p.dots=make('path',{class:'vertices'});p.group.append(p.fill,p.wire,p.dots);this.scene.append(p.group)}
      if(def.engraved)for(const p of this.parts){p.hatchPath=make('path',{class:'hatching'});p.inkEcho=make('path',{class:'ink-echo'});p.group.insertBefore(p.hatchPath,p.wire);p.group.append(p.inkEcho)}
      const scan=make('g',{stroke:'#e8b04a','stroke-opacity':'.045','stroke-width':'.6','pointer-events':'none'});for(let y=42;y<420;y+=5)scan.append(make('path',{d:`M60 ${y}H440`}));clipped.append(scan);this.svg.append(clipped);
      this.labels=make('g',{class:'labels','aria-hidden':'true'});
      this.parts.forEach((p,i)=>{const left=i%2===0,row=Math.floor(i/2),count=Math.ceil(this.parts.length/2);p.labelPos=[left?65:435,160+row*(140/Math.max(1,count-1))];p.leader=make('path',{class:'leader'});p.labelNode=make('text',{x:p.labelPos[0],y:p.labelPos[1]-6,'text-anchor':left?'start':'end',class:'label'},p.label);this.labels.append(p.leader,p.labelNode)});this.svg.append(this.labels);
      const base=make('g');base.append(make('path',{d:'M206 453 L140 300 M294 453 L360 300',stroke:'#e8b04a','stroke-opacity':'.09',fill:'none'}),make('ellipse',{cx:250,cy:461,rx:62,ry:12,fill:'#372616',stroke:'#82602f'}),make('ellipse',{cx:250,cy:455,rx:62,ry:12,fill:`url(#${this.uid}-brass)`,stroke:'#be934e'}),make('ellipse',{cx:250,cy:454,rx:43,ry:7,fill:'#251b11',stroke:'#d3a14c'}),make('ellipse',{cx:250,cy:453,rx:29,ry:3,fill:'#e8b04a','fill-opacity':'.25',stroke:'#f5d27a','stroke-width':'.7'}));if(!this.hasAttribute('compact'))this.svg.append(base);
      this.button.onpointerenter=e=>{if(e.pointerType!=='touch')this.hovered=true};this.button.onpointerleave=()=>this.hovered=false;
      this.button.onfocus=()=>this.focused=true;this.button.onblur=()=>this.focused=false;
      this.button.onclick=()=>{this.pinned=!this.pinned;this.button.setAttribute('aria-pressed',String(this.pinned))};
      this.observer=new IntersectionObserver(([entry])=>{this.visible=entry.isIntersecting});this.observer.observe(this);
      this.previous=0;this.render(0);this.frame=requestAnimationFrame(t=>this.tick(t));
    }
    addBackdropOptions(clipped,defs,initialBackdrop='spotlight'){
      // Independent, static SVG layers: never rebuild or rotate the model on selection.
      const uid=this.uid;
      const light=make('radialGradient',{id:uid+'-spot'});
      light.append(make('stop',{offset:'0%','stop-color':'#fff6da','stop-opacity':'.98'}),make('stop',{offset:'52%','stop-color':'#fff0c7','stop-opacity':'.74'}),make('stop',{offset:'100%','stop-color':'#fff0c7','stop-opacity':'0'}));defs.append(light);
      const fade=make('radialGradient',{id:uid+'-quiet-center'});
      fade.append(make('stop',{offset:'0%','stop-color':'#111'}),make('stop',{offset:'40%','stop-color':'#333'}),make('stop',{offset:'75%','stop-color':'#fff'}));defs.append(fade);
      const mask=make('mask',{id:uid+'-backdrop-mask',maskUnits:'userSpaceOnUse',x:50,y:30,width:400,height:400});mask.append(make('circle',{cx:250,cy:230,r:190,fill:`url(#${uid}-quiet-center)`}));defs.append(mask);
      const backdrop=make('g',{'aria-hidden':'true','pointer-events':'none',opacity:'.65'});clipped.append(backdrop);
      // Negative intensity is an ink wash, not an invalid negative SVG opacity.
      const ink=make('filter',{id:uid+'-negative-ink','color-interpolation-filters':'sRGB'});
      ink.append(make('feColorMatrix',{type:'matrix',values:'0 0 0 0 0.30  0 0 0 0 0.18  0 0 0 0 0.08  0 0 0 0.65 0'}));defs.append(ink);
      const layers={};
      for(const name of ['spotlight','grid','halo','grain']){layers[name]=make('g',{visibility:name===initialBackdrop?'visible':'hidden'});backdrop.append(layers[name])}
      layers.spotlight.append(make('ellipse',{cx:250,cy:226,rx:170,ry:164,fill:`url(#${uid}-spot)`}),make('path',{d:'M219 420 L142 168 Q250 124 358 168 L281 420 Z',fill:`url(#${uid}-spot)`,opacity:'.45'}));
      const grid=make('g',{mask:`url(#${uid}-backdrop-mask)`,stroke:'#795525','stroke-width':'.65','stroke-opacity':'.32',fill:'none'});
      for(let n=62;n<=438;n+=20){grid.append(make('path',{d:`M${n} 42V418 M62 ${n}H438`}))}
      for(const r of [100,160])grid.append(make('circle',{cx:250,cy:230,r,'stroke-dasharray':'2 5','stroke-opacity':'.65'}));layers.grid.append(grid);
      const halo=make('g',{stroke:'#76502c',fill:'none','stroke-opacity':'.32','stroke-linecap':'round'});
      for(const r of [112,117,163,167])halo.append(make('circle',{cx:250,cy:230,r,'stroke-width':r===117?.9:.5}));
      for(let i=0;i<100;i++){const a=TAU*i/100,r=121+(i%5)*2;halo.append(make('path',{d:`M${250+Math.cos(a)*r} ${230+Math.sin(a)*r}Q${250+Math.cos(a+.016)*142} ${230+Math.sin(a+.016)*142} ${250+Math.cos(a+.025)*159} ${230+Math.sin(a+.025)*159}`,'stroke-width':i%5?.45:.8}))}layers.halo.append(halo);
      for(let i=0;i<230;i++){
        const x=63+(i*83.37)%374,y=43+(i*137.71)%374;
        layers.grain.append(make('path',{d:`M${x.toFixed(1)} ${y.toFixed(1)}l${(1+i%4)*.8} ${i%2?.45:-.45}`,stroke:'#76502c','stroke-width':i%7?.5:.8,'stroke-opacity':'.19','stroke-linecap':'round'}));
      }
      layers.grain.append(make('ellipse',{cx:250,cy:230,rx:145,ry:160,fill:`url(#${uid}-spot)`,opacity:'.28'}));
      const controls=document.createElement('div');controls.className='backdrop-controls';
      controls.innerHTML=`<div class="control-row"><label for="${uid}-backdrop">Backdrop study</label><select id="${uid}-backdrop"><option value="plain">Original / plain</option><option value="spotlight" selected>Warm spotlight</option><option value="grid">Drafting grid</option><option value="halo">Engraved halo</option><option value="grain">Paper grain</option></select></div><div class="control-row"><label for="${uid}-strength">Intensity</label><input id="${uid}-strength" type="range" min="-100" max="100" value="65"><output for="${uid}-strength">+65%</output></div><small>Negative: dark ink wash Â· 0: no backdrop Â· Positive: original effect</small>`;
      this.shadowRoot.querySelector('.instrument').append(controls);
      const select=controls.querySelector('select'),slider=controls.querySelector('input'),output=controls.querySelector('output');
      select.value=initialBackdrop;
      select.onchange=()=>{for(const [name,layer]of Object.entries(layers))layer.setAttribute('visibility',name===select.value?'visible':'hidden');slider.disabled=select.value==='plain'};
      slider.oninput=()=>{
        const value=Number(slider.value);
        backdrop.setAttribute('opacity',String(Math.abs(value)/100));
        if(value<0)backdrop.setAttribute('filter',`url(#${uid}-negative-ink)`);else backdrop.removeAttribute('filter');
        output.value=(value>0?'+':'')+value+'%';
      };
    }
    tick(now){
      const dt=this.previous?Math.min((now-this.previous)/1000,.05):0;this.previous=now;
      if(this.visible&&!document.hidden){const target=this.pinned||this.hovered||this.focused?1:0;
        this.amount=this.motion.matches?target:this.amount+(target-this.amount)*(1-Math.exp(-dt*5));
        if(!this.motion.matches)this.time+=dt;
        this.button.classList.toggle('expanded',!!target);
        if(!this.motion.matches||this.lastAmount!==this.amount){this.render(this.time);this.lastAmount=this.amount}
      }
      this.frame=requestAnimationFrame(t=>this.tick(t));
    }
    render(time){
      const compact=this.hasAttribute('compact');
      const turn=compact?-.32+(this.motion.matches?0:Math.sin(time*.3)*.22):this.motion.matches?-.55:time*TAU/20-.55;
      const zoom=compact?1.75-this.amount*.35:1.06;
      const project=p=>{const [x,y,z]=rotate(rotate(p,[0,turn,0]),[compact?-.35:-.23,0,-.04]),s=zoom*700/(700-z);return [250+x*s,230+y*s,z]};
      const coordinate=p=>`${p[0].toFixed(1)},${p[1].toFixed(1)}`;
      const ordered=[];
      for(let i=0;i<this.parts.length;i++){
        const p=this.parts[i],drift=this.motion.matches?0:Math.sin(time*.85+i*.68)*2;
        const offset=add(p.position,p.axis.map(v=>v*(p.amount*this.amount+drift)));
        const pts=p.points.map(v=>project(add(v,offset)));
        p.wire.setAttribute('d',p.lines.map(ids=>'M'+ids.map(n=>coordinate(pts[n])).join('L')).join(''));
        if(this.def.engraved){
          p.hatchPath.setAttribute('d',(p.hatching||[]).map(ids=>'M'+ids.map(n=>coordinate(pts[n])).join('L')).join(''));
          p.inkEcho.setAttribute('d',p.lines.map((ids,j)=>'M'+ids.map(n=>coordinate([pts[n][0]+.5*Math.sin(n*1.3+j),pts[n][1]+.45*Math.cos(n*.8+j)])).join('L')).join(''));
        }
        p.fill.setAttribute('d',p.faces.map(ids=>'M'+ids.map(n=>coordinate(pts[n])).join('L')+'Z').join(''));
        p.dots.setAttribute('d',pts.filter((_,n)=>n%5===0).map(q=>`M${coordinate(q)}h.01`).join(''));
        const center=project(offset),[x,y]=p.labelPos;
        p.leader.setAttribute('d',`M${coordinate(center)}L${x<250?x+35:x-35},${y}H${x}`);
        ordered.push({p,z:center[2]});
      }
      // Painter order preserves translucent layers as the assembly turns.
      ordered.sort((a,b)=>a.z-b.z);const order=ordered.map(x=>x.p.label).join('|');
      if(this.order!==order){ordered.forEach(({p})=>this.scene.append(p.group));this.order=order}
    }
  }
  // Avoid duplicate registration when the dashboard reloads a development module.
  if (!customElements.get('hologram-display')) customElements.define('hologram-display',HologramDisplay);
})();
