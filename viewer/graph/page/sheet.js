/* The sheet: a bottom sheet under 768 px, a side panel above (that is CSS). It shows ONE thing at a time: a card (either
   the page's own <article> from the markup, moved in with appendChild and moved back to a placeholder comment on close, R2;
   or a div.card the page made from the data, which has no place in the page, so on close it is removed, not moved back),
   the About content (builder markup, moved the same way) or the key (generated). The List markup is never copied or reparsed.

   CLASS TABLE this module sets or honours (all fixed here, none from data):
     graph-sheet        on the sheet element (the comment script finds it with article.closest('.graph-sheet'))
     comments-editing   set and removed ONLY by the comment script; graph.css makes the sheet full height with it
     graph-sheet-body   the body container; its SINGLE child is the moved root (a card's root: its <article>, or the div.card
                        the page made; the About block's root, or the generated key); `sheetclose` is dispatched on that root,
                        `sheetcloserequest` from anywhere in it runs close()
     claim-clamped      on the sheet body while the claim is clamped to 10 lines (graph.css)
     sheet-status, sheet-tool, crumbs, crumb, crumb-here, crumb-role   chrome this module creates
     note-label, note-source, note-body   the repository's note, only when the card has one (info.note), directly after the status line (and after info.lead)
     info.lead / info.tail   arrays of nodes the page built (statement.js): lead goes between the status line and the note, tail after the note; both
                        are released with the note's nodes
     note-typeset-line, note-toggle   only when the page says the maths face is on (info.note.typeset): the line under the source line (told only of
                        the maths-type view) and the button that swaps the rendering for the exact text and back (aria-pressed true = exact text);
                        note-exact on the body while the exact text is shown. A card shown again always starts on the rendering.

   CLOSING: every way the sheet closes goes through close(), the ONE close function. It first dispatches a cancelable
   `sheetclose` event on the thing shown; if a listener cancels it, the sheet stays open and nothing moves. A
   bubbling `sheetcloserequest` from inside the sheet runs the same close(). */
import { el, titleChildren } from "./dom.js";
import { renderNote, exactNote } from "./note.js";

/* The parts button's two words for a card of `kind`: the kind row's open_words (kind -> {open, close}, strings keys) when it has one, else open_parts and
   close_parts exactly as before. The page names no kind: the table row decides. */
export function partsWords(strings, openWords, kind) {
  const row = openWords && typeof kind === "string" && Object.prototype.hasOwnProperty.call(openWords, kind) ? openWords[kind] : null;
  return row ? { open: strings[row.open], close: strings[row.close] } : { open: strings.open_parts, close: strings.close_parts };
}

export function createSheet(parts, strings, hooks, signal) {
  const { root, crumbs, tools, body, closeButton } = parts;
  const doc = root.ownerDocument;
  const win = doc.defaultView;
  let cur = null;   // { node, home, details: [{d, open}], status, noteEls, id (a card), parts, partsOpen }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function restoreDetails(rec) {
    for (const x of rec.details) x.d.open = x.open;
  }

  /* The restore half of close(): everything moved or added goes back, so the page's markup is as it was. */
  function release(rec) {
    if (rec.status && rec.status.parentNode) rec.status.parentNode.removeChild(rec.status);
    for (const x of rec.noteEls || []) if (x.parentNode) x.parentNode.removeChild(x);
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
    if (rec.sheetClass) root.classList.remove(rec.sheetClass);
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

  /* Both callers (showCard and showPanel) call close() before adopt, so a card the page made is always parentless when adopted
     and gets no home comment. A future route that adopted a made card while it was still in the sheet body would give it a home
     comment, and release would then leave the card behind. The browser cell that catches it is the reopen case
     c_made_close_reopen (made B3), which expects the same element back with one child. */
  function adopt(node, moveHome) {
    const rec = { node, home: null, details: [], status: null };
    if (moveHome && node.parentNode) {   // a card the page made has no home in the page: on close it leaves (release removes a parentless card)
      rec.home = doc.createComment("");
      node.parentNode.insertBefore(rec.home, node);
    }
    node.querySelectorAll("details").forEach((d) => { rec.details.push({ d, open: d.open }); d.open = false; });
    body.appendChild(node);
    root.hidden = false;
    cur = rec;
    return rec;
  }

  /* The last entry is the open card itself (not a link) unless the page says the list stops at the parent (currentListed false): then every
     entry is an ancestor and stays a link. */
  function crumbList(list, currentListed) {
    const items = list.map((c, i) => {
      const last = currentListed && i === list.length - 1;
      const kids = [];
      if (typeof c.role === "string" && c.role !== "") kids.push(el("span", { class: "crumb-role" }, [c.role]));
      kids.push(...titleChildren(c.title));
      return el("li", {}, [last ? el("span", { class: "crumb-here" }, kids) : el("button", { type: "button", class: "crumb", "data-id": c.id }, kids)]);
    });
    if (items.length === 0) return null;   // no ancestor, no landmark: an empty labelled nav is noise to a screen reader
    return el("nav", { "aria-label": strings.crumb_label, class: "crumbs" }, [el("ol", {}, items)]);
  }

  /* showCard / showPanel return false when the current content refused to close. */
  function showCard(article, info) {
    if (!close()) return false;
    const rec = adopt(article, true);
    rec.id = info.id;          // the id this sheet shows: an engine event about any other id never touches it
    if (info.sheetClass) { root.classList.add(info.sheetClass); rec.sheetClass = info.sheetClass; }   // a token from the page's own table
    clear(crumbs);
    const nav = crumbList(info.crumbs, info.currentListed !== false);
    if (nav) crumbs.appendChild(nav);
    const claim = article.querySelector(".claim");
    /* The status line is built only for a non-empty status: a null or empty status gets no element (the page's
       own path always passes a string today), so the release step finds rec.status null and the card's own content is first under the title. */
    if (typeof info.status === "string" && info.status !== "") {
      rec.status = el("p", { class: "sheet-status" }, [info.status]);
      if (claim && claim.parentNode) claim.parentNode.insertBefore(rec.status, claim.nextSibling);
      else article.insertBefore(rec.status, article.firstChild);
    }
    /* The repository's note, when the card has one: the label, the source line (text only, never a link), then the note rendered by note.js. They go
       directly after the status line (after the claim when there is none), and the restore half of close takes them out again. */
    const lead = info.lead || [], tail = info.tail || [];
    let noteKids = [];
    if (info.note) {
      const n = info.note, t = n.typeset || null;
      const label = el("p", { class: "note-label" }, [t ? t.label : n.label]);
      const source = el("p", { class: "note-source" }, n.sourceParts);
      const noteBody = el("div", { class: "note-body" }, []);
      noteBody.appendChild(renderNote(n.text, el, !!t));
      const kids = [label, source];
      if (t) {
        /* The maths-face view: the line and the button, and one function that sets everything the two views differ in. */
        const line = el("p", { class: "note-typeset-line" }, [t.line]);
        const toggle = el("button", { type: "button", class: "note-toggle", "aria-pressed": "false" }, [t.exactButton]);
        let exact = false;
        const setView = (showExact) => {
          exact = showExact;
          clear(label); label.appendChild(doc.createTextNode(exact ? n.label : t.label));
          clear(noteBody);
          noteBody.appendChild(exact ? exactNote(n.text, el) : renderNote(n.text, el, true));
          noteBody.classList.toggle("note-exact", exact);
          clear(toggle); toggle.appendChild(doc.createTextNode(exact ? t.renderButton : t.exactButton));
          toggle.setAttribute("aria-pressed", exact ? "true" : "false");
          if (exact && line.parentNode) line.parentNode.removeChild(line);
          else if (!exact && !line.parentNode && source.parentNode) source.parentNode.insertBefore(line, source.nextSibling);
        };
        toggle.addEventListener("click", () => setView(!exact), { signal });
        kids.push(line, toggle);
      }
      kids.push(noteBody);
      noteKids = kids;
    }
    const placed = [...lead, ...noteKids, ...tail];
    if (placed.length) {
      rec.noteEls = placed;
      const first = article.firstChild;
      let after = rec.status || (claim && claim.parentNode ? claim : null);
      for (const k of placed) {
        if (after) { after.parentNode.insertBefore(k, after.nextSibling); after = k; } else article.insertBefore(k, first);
      }
    }
    clear(tools);
    if (info.canParts) {
      const w = info.partsWords || { open: strings.open_parts, close: strings.close_parts };   // a kind row's open_words (app.js), else the live words
      const b = el("button", { type: "button", class: "sheet-tool" }, [info.partsOpen ? w.close : w.open]);
      rec.partsOpen = !!info.partsOpen;
      rec.partsWords = w;
      b.addEventListener("click", () => (rec.partsOpen ? hooks.closeParts(info.id) : hooks.openParts(info.id)), { signal });
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
     the card itself gets no class, style or attribute from us. */
  function clamp(claim) {
    if (!claim) return;
    body.classList.add("claim-clamped");
    if (claim.scrollHeight <= claim.clientHeight + 1) { body.classList.remove("claim-clamped"); return; }
    const b = el("button", { type: "button", class: "sheet-tool" }, [strings.claim_more]);
    b.addEventListener("click", () => {
      const clamped = body.classList.toggle("claim-clamped");
      clear(b);
      b.appendChild(doc.createTextNode(clamped ? strings.claim_more : strings.claim_less));
    }, { signal });
    tools.appendChild(b);
  }

  /* One more control for the tool strip of what is showing (the page's own, for example the way back to the graph). The strip is cleared whenever another card or panel
     is shown or the sheet closes, so the control goes with what it was added to. False when nothing is showing. */
  function appendTool(control) {
    if (!cur) return false;
    tools.appendChild(control);
    return true;
  }

  /* The parts button always reflects the open state of the SHOWN id: an event for any other id changes nothing. */
  function setPartsOpen(id, open) {
    if (!cur || !cur.parts || cur.id !== id) return;
    cur.partsOpen = !!open;
    clear(cur.parts);
    cur.parts.appendChild(doc.createTextNode(open ? cur.partsWords.close : cur.partsWords.open));
  }

  closeButton.addEventListener("click", () => hooks.closeButton(), { signal });
  root.addEventListener("sheetcloserequest", () => close(), { signal });
  crumbs.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest("button[data-id]");
    if (b) hooks.go(b.getAttribute("data-id"));
  }, { signal });
  body.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a");
    const h = a && a.getAttribute("href");
    if (h && h.charAt(0) === "#") { e.preventDefault(); hooks.go(h.slice(1)); }
  }, { signal });

  return {
    close, dispose, showCard, showPanel, setPartsOpen, appendTool,
    isOpen: () => cur !== null,
    shown: () => (cur ? cur.node : null),
  };
}
