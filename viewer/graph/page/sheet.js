/* The sheet: a bottom sheet under 768 px, a side panel above (that is CSS). It shows ONE thing at a time: a card's
   own <article> (moved in with appendChild and moved back to a placeholder comment on close, R2), the About
   content (builder markup, moved the same way) or the key (generated). The List markup is never copied or reparsed.

   CLASS TABLE this module sets or honours (all fixed here, none from data):
     graph-sheet        on the sheet element (the comment script finds it with article.closest('.graph-sheet'))
     comments-editing   set and removed ONLY by the comment script; graph.css makes the sheet full height with it
     graph-sheet-body   the body container; its SINGLE child is the moved root (a card's <article>, the About block's root,
                        or the generated key); `sheetclose` is dispatched on that root, `sheetcloserequest` from anywhere in it
                        runs close()
     claim-clamped      on the sheet body while the claim is clamped to 10 lines (graph.css)
     sheet-status, sheet-tool, crumbs, crumb, crumb-here, crumb-role   chrome this module creates

   CLOSING: every way the sheet closes goes through close(), the ONE close function. It first dispatches a cancelable
   `sheetclose` event on the thing shown; if a listener cancels it, the sheet stays open and nothing moves. A
   bubbling `sheetcloserequest` from inside the sheet runs the same close(). */
import { el } from "./dom.js";

export function createSheet(parts, strings, hooks) {
  const { root, crumbs, tools, body, closeButton } = parts;
  const doc = root.ownerDocument;
  const win = doc.defaultView;
  let cur = null;   // { node, home, details: [{d, open}], status, kind }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function restoreDetails(rec) {
    for (const x of rec.details) x.d.open = x.open;
  }

  /* The restore half of close(): everything moved or added goes back, so the page's markup is as it was. */
  function release(rec) {
    if (rec.status && rec.status.parentNode) rec.status.parentNode.removeChild(rec.status);
    restoreDetails(rec);
    if (rec.home) {
      if (rec.home.parentNode) {
        rec.home.parentNode.insertBefore(rec.node, rec.home);
        rec.home.parentNode.removeChild(rec.home);
      }
    } else if (rec.node.parentNode) {
      rec.node.parentNode.removeChild(rec.node);
    }
    clear(crumbs);
    clear(tools);
    body.classList.remove("claim-clamped");
    root.hidden = true;
    cur = null;
  }

  function close() {
    if (!cur) return true;
    const ev = new win.CustomEvent("sheetclose", { cancelable: true });
    cur.node.dispatchEvent(ev);
    if (ev.defaultPrevented) return false;
    release(cur);
    return true;
  }

  /* For the fallback only: put everything home even if a listener would have cancelled. */
  function dispose() { if (cur) release(cur); }

  function adopt(node, moveHome) {
    const rec = { node, home: null, details: [], status: null };
    if (moveHome) {
      rec.home = doc.createComment("");
      node.parentNode.insertBefore(rec.home, node);
    }
    node.querySelectorAll("details").forEach((d) => { rec.details.push({ d, open: d.open }); d.open = false; });
    body.appendChild(node);
    root.hidden = false;
    cur = rec;
    return rec;
  }

  function crumbList(list) {
    const items = list.map((c, i) => {
      const last = i === list.length - 1;
      const kids = [];
      if (typeof c.role === "string" && c.role !== "") kids.push(el("span", { class: "crumb-role" }, [c.role]));
      kids.push(c.title);
      return el("li", {}, [last ? el("span", { class: "crumb-here" }, kids) : el("button", { type: "button", class: "crumb", "data-id": c.id }, kids)]);
    });
    return el("nav", { "aria-label": strings.crumb_label, class: "crumbs" }, [el("ol", {}, items)]);
  }

  /* showCard / showPanel return false when the current content refused to close. */
  function showCard(article, info) {
    if (!close()) return false;
    const rec = adopt(article, true);
    clear(crumbs);
    crumbs.appendChild(crumbList(info.crumbs));
    const claim = article.querySelector(".claim");
    rec.status = el("p", { class: "sheet-status" }, [info.status]);
    if (claim && claim.parentNode) claim.parentNode.insertBefore(rec.status, claim.nextSibling);
    else article.insertBefore(rec.status, article.firstChild);
    clear(tools);
    if (info.canParts) {
      const b = el("button", { type: "button", class: "sheet-tool" }, [info.partsOpen ? strings.close_parts : strings.open_parts]);
      rec.partsOpen = !!info.partsOpen;
      b.addEventListener("click", () => (rec.partsOpen ? hooks.closeParts(info.id) : hooks.openParts(info.id)));
      rec.parts = b;
      tools.appendChild(b);
    }
    clamp(claim);
    body.scrollTop = 0;
    return true;
  }

  function showPanel(node, homeIt) {
    if (!close()) return false;
    adopt(node, homeIt);
    clear(crumbs);
    clear(tools);
    body.scrollTop = 0;
    return true;
  }

  /* A claim taller than 10 lines shows 10 and a 'Show the whole claim' button. The clamp is a class on the body, so
     the article itself gets no class, style or attribute from us. */
  function clamp(claim) {
    if (!claim) return;
    body.classList.add("claim-clamped");
    if (claim.scrollHeight <= claim.clientHeight + 1) { body.classList.remove("claim-clamped"); return; }
    const b = el("button", { type: "button", class: "sheet-tool" }, [strings.claim_more]);
    b.addEventListener("click", () => {
      const clamped = body.classList.toggle("claim-clamped");
      clear(b);
      b.appendChild(doc.createTextNode(clamped ? strings.claim_more : strings.claim_less));
    });
    tools.appendChild(b);
  }

  function setPartsOpen(id, open) {
    if (!cur || !cur.parts) return;
    cur.partsOpen = !!open;
    clear(cur.parts);
    cur.parts.appendChild(doc.createTextNode(open ? strings.close_parts : strings.open_parts));
  }

  closeButton.addEventListener("click", () => hooks.closeButton());
  root.addEventListener("sheetcloserequest", () => close());
  crumbs.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest("button[data-id]");
    if (b) hooks.go(b.getAttribute("data-id"));
  });
  body.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a");
    const h = a && a.getAttribute("href");
    if (h && h.charAt(0) === "#") { e.preventDefault(); hooks.go(h.slice(1)); }
  });

  return {
    close, dispose, showCard, showPanel, setPartsOpen,
    isOpen: () => cur !== null,
    shown: () => (cur ? cur.node : null),
  };
}
