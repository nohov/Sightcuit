// Inventory drawer: a brass tab at the bottom of the dashboard slides a gallery
// of every identified device up over the page.

import { useEffect, useRef, useState } from "react";
import { DEVICES, lookup } from "../devices.js";
import DeviceModel from "./DeviceModels.jsx";

const TOP_METALS = 3;

function timeAgo(ms) {
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return new Date(ms).toLocaleDateString();
}

const Chevron = ({ up }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={up ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"} />
  </svg>
);

function ItemCard({ item, onRemove }) {
  const device = lookup(item.id);
  const known = Boolean(DEVICES[item.id]);
  const metals = Object.entries(device.metals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_METALS);
  return (
    <article className="inv-card">
      <div className="inv-thumb">
        {item.thumb ? (
          <img src={item.thumb} alt={`Snapshot of ${item.name}`} />
        ) : (
          <div className="inv-model" role="img" aria-label={`Model of ${device.label}`}>
            <div className="model-scale">
              <DeviceModel id={known ? item.id : null} />
            </div>
          </div>
        )}
        <span className="inv-rivet tl" />
        <span className="inv-rivet tr" />
        <span className="inv-rivet bl" />
        <span className="inv-rivet br" />
      </div>
      <div className="inv-plate mono">{item.name}</div>
      <div className="inv-body">
        <div className="inv-meta">
          <span>{device.label}</span>
          <span className="mono">
            seen {item.sightings}× · {timeAgo(item.lastSeen)}
          </span>
        </div>
        <p className="inv-desc">{item.description || "No description yet."}</p>
        {metals.length > 0 && (
          <ul className="inv-metals" aria-label="Top metals">
            {metals.map(([name, grams]) => (
              <li key={name}>
                <span>{name}</span>
                <span className="mono">{grams} g</span>
              </li>
            ))}
          </ul>
        )}
        {device.dims && (
          <div className="inv-dims mono">
            {device.dims.join(" × ")} mm · {device.weight} g
          </div>
        )}
      </div>
      <button type="button" className="inv-remove" aria-label={`Remove ${item.name} from inventory`} onClick={() => onRemove(item.key)}>
        ×
      </button>
    </article>
  );
}

export default function Inventory({ items, onClear, onRemove }) {
  const [open, setOpen] = useState(false);
  const closeRef = useRef(null);
  const tabRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const close = () => {
    setOpen(false);
    tabRef.current?.focus();
  };

  return (
    <>
      <button
        ref={tabRef}
        type="button"
        className={`inv-tab ${open ? "hidden" : ""}`}
        aria-expanded={open}
        aria-controls="inventory-drawer"
        onClick={() => setOpen(true)}
      >
        <Chevron up />
        Inventory
        <span className="inv-count mono">{items.length}</span>
      </button>

      <div className={`inv-backdrop ${open ? "open" : ""}`} onClick={close} aria-hidden="true" />
      <section
        id="inventory-drawer"
        className={`inv-drawer ${open ? "open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Inventory"
        aria-hidden={!open}
      >
        <header className="inv-head">
          <div>
            <h2>Inventory</h2>
            <div className="mono muted">
              {items.length} item{items.length === 1 ? "" : "s"} identified
            </div>
          </div>
          <div className="inv-actions">
            {items.length > 0 && (
              <button type="button" className="text-btn" onClick={onClear} tabIndex={open ? 0 : -1}>
                Clear all
              </button>
            )}
            <button ref={closeRef} type="button" className="text-btn primary inv-close" onClick={close} tabIndex={open ? 0 : -1}>
              <Chevron />
              Back to dashboard
            </button>
          </div>
        </header>

        {items.length === 0 ? (
          <p className="inv-empty">Nothing identified yet. Devices the glasses recognise are collected here.</p>
        ) : (
          <div className="inv-grid">
            {items.map((item) => (
              <ItemCard item={item} key={item.key} onRemove={onRemove} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
