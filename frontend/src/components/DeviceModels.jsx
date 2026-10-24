// Rotating device models drawn with CSS 3D transforms: each model is a set of
// flat panels placed in 3D space around the origin of a preserve-3d container.
// No WebGL or model files needed. Swap for three.js + .glb files later if
// higher fidelity is wanted.

const F = ({ className = "", style, children }) => (
  <div className={`p ${className}`} style={style}>
    {children}
  </div>
);

const range = (n) => Array.from({ length: n }, (_, i) => i);

function Laptop() {
  return (
    <>
      {/* keyboard deck */}
      <F className="solid bf" style={{ left: -75, top: -50, width: 150, height: 100, borderRadius: 5, transform: "translateY(25px) rotateX(90deg)" }}>
        <F className="keys" style={{ left: 10, top: 8, width: 130, height: 50 }} />
        <F className="pad" style={{ left: 50, top: 64, width: 50, height: 28 }} />
      </F>
      {/* underside with feet */}
      <F className="solid bf" style={{ left: -75, top: -50, width: 150, height: 100, borderRadius: 5, transform: "translateY(31px) rotateX(-90deg)" }}>
        {[[12, 10], [130, 10], [12, 82], [130, 82]].map(([l, t]) => (
          <F key={`${l}-${t}`} className="foot" style={{ left: l, top: t, width: 8, height: 8 }} />
        ))}
      </F>
      {/* base edges */}
      <F className="side" style={{ left: -75, top: -3, width: 150, height: 6, transform: "translateY(28px) translateZ(50px)" }} />
      <F className="side" style={{ left: -75, top: -3, width: 150, height: 6, transform: "translateY(28px) rotateY(180deg) translateZ(50px)" }} />
      <F className="side" style={{ left: -50, top: -3, width: 100, height: 6, transform: "translateY(28px) rotateY(90deg) translateZ(75px)" }}>
        <F className="port" style={{ left: 20, top: 1, width: 8, height: 3 }} />
        <F className="port" style={{ left: 32, top: 1, width: 8, height: 3 }} />
      </F>
      <F className="side" style={{ left: -50, top: -3, width: 100, height: 6, transform: "translateY(28px) rotateY(-90deg) translateZ(75px)" }} />
      {/* display */}
      <F className="screen bf" style={{ left: -75, top: -47.5, width: 150, height: 95, borderRadius: 5, transformOrigin: "50% 100%", transform: "translateY(-22.5px) translateZ(-47px) rotateX(12deg)" }}>
        <F className="glass" style={{ left: 6, top: 6, width: 138, height: 80 }}>
          <F className="ui" style={{ left: 10, top: 10, width: 60, height: 5 }} />
          <F className="ui-line" style={{ left: 10, top: 22, width: 118, height: 30 }} />
          <F className="ui" style={{ left: 10, top: 58, width: 40, height: 12 }} />
          <F className="ui" style={{ left: 56, top: 58, width: 40, height: 12 }} />
        </F>
      </F>
      {/* lid back with emblem */}
      <F className="solid bf" style={{ left: -75, top: -47.5, width: 150, height: 95, borderRadius: 5, transformOrigin: "50% 100%", transform: "translateY(-22.5px) translateZ(-47px) rotateX(12deg) rotateY(180deg)" }}>
        <F className="ring" style={{ left: 61, top: 33, width: 28, height: 28 }} />
        <F className="dot" style={{ left: 70, top: 42, width: 10, height: 10 }} />
      </F>
    </>
  );
}

function Phone() {
  const corners = [
    [30.5, 66.5, 45],
    [30.5, -66.5, -45],
    [-30.5, 66.5, 135],
    [-30.5, -66.5, -135],
  ];
  return (
    <>
      {/* screen */}
      <F className="screen bf" style={{ left: -34, top: -70, width: 68, height: 140, borderRadius: 12, transform: "translateZ(4px)" }}>
        <F className="notch" style={{ left: 23, top: 6, width: 22, height: 7 }} />
        <F className="clock" style={{ left: 7, top: 4 }}>9:41</F>
        <F className="battery" style={{ left: 50, top: 7, width: 9, height: 4 }} />
        <F className="apps" style={{ left: 6, top: 22, width: 56, height: 84 }} />
        <F className="ui" style={{ left: 6, top: 110, width: 56, height: 16, borderRadius: 6 }} />
        <F className="homebar" style={{ left: 24, top: 131, width: 20, height: 2 }} />
      </F>
      {/* back with camera block */}
      <F className="solid bf" style={{ left: -34, top: -70, width: 68, height: 140, borderRadius: 12, transform: "rotateY(180deg) translateZ(4px)" }}>
        <F className="camera-block" style={{ left: 6, top: 6, width: 30, height: 30 }}>
          <F className="lens" style={{ left: 3, top: 3, width: 11, height: 11 }} />
          <F className="lens" style={{ left: 3, top: 15, width: 11, height: 11 }} />
          <F className="lens" style={{ left: 16, top: 9, width: 11, height: 11 }} />
          <F className="flash" style={{ left: 19, top: 22, width: 4, height: 4 }} />
        </F>
      </F>
      {/* sides with buttons */}
      <F className="side" style={{ left: -4, top: -58, width: 8, height: 116, transform: "rotateY(90deg) translateZ(34px)" }}>
        <F className="button" style={{ left: 1, top: 28, width: 6, height: 18 }} />
      </F>
      <F className="side" style={{ left: -4, top: -58, width: 8, height: 116, transform: "rotateY(-90deg) translateZ(34px)" }}>
        <F className="button" style={{ left: 1, top: 14, width: 6, height: 7 }} />
        <F className="button" style={{ left: 1, top: 26, width: 6, height: 14 }} />
        <F className="button" style={{ left: 1, top: 44, width: 6, height: 14 }} />
      </F>
      <F className="side" style={{ left: -22, top: -4, width: 44, height: 8, transform: "rotateX(90deg) translateZ(70px)" }} />
      <F className="side" style={{ left: -22, top: -4, width: 44, height: 8, transform: "rotateX(-90deg) translateZ(70px)" }}>
        <F className="port" style={{ left: 17, top: 2, width: 10, height: 4 }} />
      </F>
      {corners.map(([x, y, r]) => (
        <F key={r} className="side" style={{ left: -4, top: -8.5, width: 8, height: 17, transform: `translate(${x}px, ${y}px) rotateZ(${r}deg) rotateY(90deg)` }} />
      ))}
    </>
  );
}

function Headphones() {
  const cup = (x, outer) => (
    <>
      <F className="solid" style={{ left: -26, top: -30, width: 52, height: 60, borderRadius: 26, transform: `translateX(${x}px) translateY(30px) rotateY(90deg) translateZ(${outer}px)` }} />
      <F className="cushion" style={{ left: -22, top: -26, width: 44, height: 52, borderRadius: 22, transform: `translateX(${x}px) translateY(30px) rotateY(90deg) translateZ(${-outer}px)` }} />
      {range(4).map((i) => (
        <F key={i} className="side" style={{ left: -9, top: -2, width: 18, height: 4, transform: `translateX(${x}px) translateY(30px) rotateX(${i * 45}deg) translateY(28px)` }} />
      ))}
    </>
  );
  return (
    <>
      {/* headband: segmented arc */}
      {range(11).map((i) => {
        const a = -90 + i * 18;
        return (
          <F key={i} className="band" style={{ left: -12, top: -6, width: 24, height: 12, borderRadius: 3, transform: `translateY(-8px) rotateZ(${a}deg) translateY(-64px)` }} />
        );
      })}
      {/* sliders */}
      <F className="edge" style={{ left: -4, top: -14, width: 8, height: 28, transform: "translateX(-64px) translateY(-4px)" }} />
      <F className="edge" style={{ left: -4, top: -14, width: 8, height: 28, transform: "translateX(64px) translateY(-4px)" }} />
      {cup(-64, -9)}
      {cup(64, 9)}
    </>
  );
}

function Speaker() {
  const cap = (x, ry) => (
    <F className="solid" style={{ left: -40, top: -40, width: 80, height: 80, borderRadius: "50%", transform: `translateX(${x}px) rotateY(${ry}deg)` }}>
      <F className="ring" style={{ left: 11, top: 11, width: 58, height: 58, borderWidth: 1 }} />
      <F className="ring dark" style={{ left: 23, top: 23, width: 34, height: 34, borderWidth: 1 }} />
      <F className="dot" style={{ left: 35, top: 35, width: 10, height: 10 }} />
    </F>
  );
  return (
    <>
      {cap(-70, -90)}
      {cap(70, 90)}
      {[-62, 62].map((x) => (
        <F key={x} className="ring" style={{ left: -40, top: -40, width: 80, height: 80, borderWidth: 3, transform: `translateX(${x}px) rotateY(90deg)` }} />
      ))}
      {[-42, -21, 0, 21, 42].map((x) => (
        <F key={x} className="ring faint" style={{ left: -40, top: -40, width: 80, height: 80, transform: `translateX(${x}px) rotateY(90deg)` }} />
      ))}
      {range(6).map((i) => (
        <F key={i} className={`stave ${i % 3 === 0 ? "grille" : ""}`} style={{ left: -70, top: -40, width: 140, height: 80, transform: `rotateX(${i * 30}deg)` }} />
      ))}
      <F className="solid controls" style={{ left: -36, top: -9, width: 72, height: 18, borderRadius: 9, transform: "translateY(-41px) rotateX(90deg)" }}>
        <span className="knob" />
        <span className="knob" />
        <span className="knob big" />
        <span className="knob" />
        <span className="knob" />
      </F>
      <F className="foot-strip" style={{ left: -50, top: -6, width: 100, height: 12, transform: "translateY(41px) rotateX(90deg)" }} />
      <F className="loop" style={{ left: -7, top: -11, width: 14, height: 22, transform: "translateX(-75px) translateY(-26px) rotateY(90deg)" }} />
    </>
  );
}

function Watch() {
  const corners = [
    [18.5, 22.5, 45],
    [18.5, -22.5, -45],
    [-18.5, 22.5, 135],
    [-18.5, -22.5, -135],
  ];
  return (
    <>
      <F className="band" style={{ left: -16, top: -14, width: 32, height: 28, borderRadius: 4, transform: "translateY(-39px) translateZ(-1px) rotateX(-10deg)" }} />
      <F className="band" style={{ left: -16, top: -14, width: 32, height: 28, borderRadius: 4, transform: "translateY(-64px) translateZ(-7px) rotateX(-32deg)" }} />
      <F className="band" style={{ left: -16, top: -14, width: 32, height: 28, borderRadius: 4, transform: "translateY(39px) translateZ(-1px) rotateX(10deg)" }} />
      <F className="band" style={{ left: -16, top: -14, width: 32, height: 28, borderRadius: 4, transform: "translateY(64px) translateZ(-7px) rotateX(32deg)" }}>
        <F className="hole" style={{ left: 14, top: 6, width: 4, height: 4 }} />
        <F className="hole" style={{ left: 14, top: 16, width: 4, height: 4 }} />
      </F>
      {/* face */}
      <F className="screen bf" style={{ left: -22, top: -26, width: 44, height: 52, borderRadius: 12, transform: "translateZ(3.5px)" }}>
        <F className="activity move" style={{ left: 9, top: 6, width: 26, height: 26 }} />
        <F className="activity exercise" style={{ left: 13, top: 10, width: 18, height: 18 }} />
        <F className="activity stand" style={{ left: 17, top: 14, width: 10, height: 10 }} />
        <F className="watch-time" style={{ left: 0, right: 0, top: 35 }}>10:09</F>
      </F>
      {/* back with sensor */}
      <F className="solid bf" style={{ left: -22, top: -26, width: 44, height: 52, borderRadius: 12, transform: "rotateY(180deg) translateZ(3.5px)" }}>
        <F className="ring" style={{ left: 8, top: 12, width: 28, height: 28, borderWidth: 1 }} />
        <F className="lens" style={{ left: 16, top: 20, width: 12, height: 12 }} />
      </F>
      <F className="side" style={{ left: -3.5, top: -14, width: 7, height: 28, transform: "rotateY(90deg) translateZ(22px)" }} />
      <F className="side" style={{ left: -3.5, top: -14, width: 7, height: 28, transform: "rotateY(-90deg) translateZ(22px)" }} />
      <F className="side" style={{ left: -10, top: -3.5, width: 20, height: 7, transform: "rotateX(90deg) translateZ(26px)" }} />
      <F className="side" style={{ left: -10, top: -3.5, width: 20, height: 7, transform: "rotateX(-90deg) translateZ(26px)" }} />
      {corners.map(([x, y, r]) => (
        <F key={r} className="side" style={{ left: -3.5, top: -8.5, width: 7, height: 17, transform: `translate(${x}px, ${y}px) rotateZ(${r}deg) rotateY(90deg)` }} />
      ))}
      <F className="crown" style={{ left: -5, top: -5, width: 10, height: 10, transform: "translateX(25px) translateY(-8px) rotateY(90deg)" }} />
      <F className="button" style={{ left: -2, top: -6, width: 4, height: 12, transform: "translateX(23px) translateY(8px)" }} />
    </>
  );
}

function Unknown() {
  return (
    <>
      {range(6).map((i) => {
        const t = [
          "translateZ(40px)",
          "rotateY(180deg) translateZ(40px)",
          "rotateY(90deg) translateZ(40px)",
          "rotateY(-90deg) translateZ(40px)",
          "rotateX(90deg) translateZ(40px)",
          "rotateX(-90deg) translateZ(40px)",
        ][i];
        return (
          <F key={i} className="edge unknown-face" style={{ left: -40, top: -40, width: 80, height: 80, transform: t }}>
            ?
          </F>
        );
      })}
    </>
  );
}

const MODELS = {
  laptop: Laptop,
  phone: Phone,
  headphones: Headphones,
  speaker: Speaker,
  watch: Watch,
};

export default function DeviceModel({ id }) {
  const Model = MODELS[id] || Unknown;
  return (
    <div className="spin">
      <Model />
    </div>
  );
}
